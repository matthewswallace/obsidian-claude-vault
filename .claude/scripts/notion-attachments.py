#!/usr/bin/env python3
"""
Migrate Notion attachments to a vault-root Attachments/ folder and rewrite
every image/embed reference in the already-moved .md files.

Strategy:
  Notion/attachments/foo.png             → Attachments/_root/foo.png
  Notion/Foo/attachments/bar.png         → Attachments/Foo/bar.png
  Notion/Foo/Bar/attachments/baz.png     → Attachments/Foo/Bar/baz.png

The "attachments" path segment is dropped so the directory layout mirrors the
original Notion structure minus the explicit attachments wrapper. This keeps
filenames unique (Notion's directory layout already disambiguated them) and
makes provenance traceable.

Link rewriting handles the four forms we found in the export:
  ![[Notion/.../attachments/foo.png]]      Obsidian embed, vault-root path
  [[Notion/.../attachments/foo.png]]       Obsidian link, vault-root path
  ![alt](Notion/.../attachments/foo.png)   Markdown image, absolute-from-root
  ![alt](attachments/foo.png)              Markdown image, relative to source .md

Resolution uses the migration log to find each .md file's ORIGINAL Notion
path, then resolves relative refs against that location. URL-encoded paths
(%20 etc.) are decoded before matching.

Run with --dry-run to preview, --apply to mutate the filesystem.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parents[2]
NOTION_DIR = VAULT_ROOT / "Notion"
ATTACH_DEST_ROOT = VAULT_ROOT / "Attachments"
LOG_FILE = VAULT_ROOT / "_meta" / "notion-migration.log"
ATTACH_MAP_FILE = VAULT_ROOT / "_meta" / "notion-attachment-map.jsonl"

WIKI_EMBED_RE = re.compile(r"!\[\[([^\]]+?)\]\]")
WIKI_LINK_RE = re.compile(r"(?<!!)\[\[([^\]]+?)\]\]")
MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+?)\)")
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+?)\)")


def build_attachment_map() -> dict[str, str]:
    """Walk Notion/, return {old_vault_relative: new_vault_relative} for every
    non-markdown file that lives inside an attachments/ directory or directly
    under Notion/attachments/."""
    mapping: dict[str, str] = {}
    if not NOTION_DIR.exists():
        return mapping
    for path in NOTION_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".md":
            continue
        rel = path.relative_to(VAULT_ROOT)
        parts = list(rel.parts)
        if "attachments" not in parts:
            continue
        attach_idx = parts.index("attachments")
        prefix_parts = parts[1:attach_idx]
        new_parts = ["Attachments"]
        if not prefix_parts:
            new_parts.append("_root")
        else:
            new_parts.extend(prefix_parts)
        new_parts.extend(parts[attach_idx + 1 :])
        mapping[str(rel)] = str(Path(*new_parts))
    return mapping


def parse_migration_log() -> dict[str, str]:
    """Return {new_vault_path: old_notion_relative_path} for every successful
    move. old_notion_relative_path is relative to Notion/ (matches migration
    log column 4)."""
    out: dict[str, str] = {}
    if not LOG_FILE.exists():
        return out
    with LOG_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            _ts, _id, _sha, src_rel, _arrow, dest_rel = parts
            out[dest_rel] = src_rel
    return out


def resolve_ref(ref: str, md_old_notion_rel: str) -> str | None:
    """Try to turn a link target into the vault-relative key used by the
    attachment map. Returns None if it doesn't look like an attachment."""
    ref = ref.strip()
    if "|" in ref:
        ref = ref.split("|", 1)[0]
    if "#" in ref:
        ref = ref.split("#", 1)[0]
    ref = urllib.parse.unquote(ref)

    md_old_parent = Path("Notion") / Path(md_old_notion_rel).parent

    if ref.startswith("Notion/") or ref.startswith("./Notion/"):
        candidate = ref.lstrip("./")
    elif ref.startswith("/"):
        candidate = ref.lstrip("/")
    else:
        try:
            candidate = str((md_old_parent / ref).resolve().relative_to(VAULT_ROOT))
        except (ValueError, OSError):
            candidate = str(md_old_parent / ref)
    candidate = candidate.replace("\\", "/")
    return candidate


def rewrite_md_body(body: str, md_old_notion_rel: str,
                    attach_map: dict[str, str]) -> tuple[str, int]:
    hits = 0

    def make_wiki_embed(new_path: str) -> str:
        return f"![[{new_path}]]"

    def repl_wiki_embed(m: re.Match) -> str:
        nonlocal hits
        target = m.group(1)
        candidate = resolve_ref(target, md_old_notion_rel)
        new = attach_map.get(candidate) if candidate else None
        if new:
            hits += 1
            return make_wiki_embed(new)
        return m.group(0)

    def repl_wiki_link(m: re.Match) -> str:
        nonlocal hits
        target = m.group(1)
        candidate = resolve_ref(target, md_old_notion_rel)
        new = attach_map.get(candidate) if candidate else None
        if new:
            hits += 1
            return f"[[{new}]]"
        return m.group(0)

    def repl_md_img(m: re.Match) -> str:
        nonlocal hits
        target = m.group(2)
        candidate = resolve_ref(target, md_old_notion_rel)
        new = attach_map.get(candidate) if candidate else None
        if new:
            hits += 1
            return make_wiki_embed(new)
        return m.group(0)

    def repl_md_link(m: re.Match) -> str:
        nonlocal hits
        target = m.group(2)
        candidate = resolve_ref(target, md_old_notion_rel)
        new = attach_map.get(candidate) if candidate else None
        if new:
            hits += 1
            return f"[[{new}|{m.group(1)}]]"
        return m.group(0)

    body = WIKI_EMBED_RE.sub(repl_wiki_embed, body)
    body = WIKI_LINK_RE.sub(repl_wiki_link, body)
    body = MD_IMG_RE.sub(repl_md_img, body)
    body = MD_LINK_RE.sub(repl_md_link, body)
    return body, hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply", file=sys.stderr)
        return 2

    attach_map = build_attachment_map()
    print(f"Found {len(attach_map)} attachment files to migrate")

    log = parse_migration_log()
    print(f"Migration log has {len(log)} moves to consider for rewriting")

    if args.apply:
        ATTACH_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ATTACH_MAP_FILE.open("w", encoding="utf-8") as fh:
            for old, new in sorted(attach_map.items()):
                fh.write(json.dumps({"old": old, "new": new}) + "\n")

    moved = 0
    skipped = 0
    for old_rel, new_rel in attach_map.items():
        src = VAULT_ROOT / old_rel
        dst = VAULT_ROOT / new_rel
        if not src.exists():
            skipped += 1
            continue
        if args.dry_run:
            moved += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            i = 2
            stem = dst.stem
            while dst.exists():
                dst = dst.with_name(f"{stem} ({i}){dst.suffix}")
                i += 1
        shutil.move(str(src), str(dst))
        moved += 1
    print(f"{'Would move' if args.dry_run else 'Moved'} {moved} attachments, skipped {skipped}")

    total_hits = 0
    files_touched = 0
    rewrite_hits_per_dir: dict[str, int] = defaultdict(int)
    for dest_rel, src_rel in log.items():
        if src_rel == "manual":
            continue
        md_path = VAULT_ROOT / dest_rel
        if not md_path.exists() or md_path.suffix.lower() != ".md":
            continue
        try:
            body = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        new_body, hits = rewrite_md_body(body, src_rel, attach_map)
        if hits:
            total_hits += hits
            files_touched += 1
            top = dest_rel.split("/", 1)[0]
            rewrite_hits_per_dir[top] += hits
            if args.apply:
                md_path.write_text(new_body, encoding="utf-8")
    print(f"{'Would rewrite' if args.dry_run else 'Rewrote'} {total_hits} links across {files_touched} files")
    for d, n in sorted(rewrite_hits_per_dir.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5}  {d}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())

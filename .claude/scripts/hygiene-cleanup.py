#!/usr/bin/env python3
"""
Hygiene cleanup: collapse doubled folders + rename parent-named index notes to _index.md.

Strategy: rename Folder/Folder.md -> Folder/_index.md and add aliases: [Folder] to
frontmatter so existing [[Folder]] wikilinks still resolve via Obsidian alias matching.
No wikilink rewrites needed.

Reversible via _meta/hygiene.log (JSONL).

Skips _archive/ and Attachments/. Idempotent.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

VAULT = Path(__file__).resolve().parents[2]
LOG = VAULT / "_meta" / "hygiene.log"

SKIP_DIR_NAMES = {".obsidian", ".claude", ".git", "_archive", "Attachments", "_meta", "node_modules"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def iter_dirs(root: Path):
    for p in root.rglob("*"):
        if not p.is_dir():
            continue
        parts = set(p.relative_to(root).parts)
        if parts & SKIP_DIR_NAMES:
            continue
        yield p


def find_parent_named_indexes(root: Path) -> list[Path]:
    out = []
    for d in iter_dirs(root):
        candidate = d / f"{d.name}.md"
        if candidate.is_file():
            out.append(candidate)
    return out


EXPLICIT_FLATTENS = [
    "Banyan Labs/operations/todo/Operations",
]


def find_doubled_folders(root: Path) -> list[Path]:
    """Return inner doubled folder (e.g. .../Leads/Leads/) + explicit flattens."""
    out = []
    for d in iter_dirs(root):
        if d.parent.name == d.name and d.parent != d:
            out.append(d)
    for rel in EXPLICIT_FLATTENS:
        p = root / rel
        if p.is_dir():
            out.append(p)
    return out


def read_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    try:
        fm = yaml.safe_load(raw) or {}
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def write_frontmatter(fm: dict, body: str) -> str:
    if not fm:
        return body
    dumped = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip()
    return f"---\n{dumped}\n---\n{body}"


def add_alias(text: str, alias: str) -> str:
    fm, body = read_frontmatter(text)
    aliases = fm.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    elif not isinstance(aliases, list):
        aliases = []
    if alias not in aliases:
        aliases.append(alias)
    fm["aliases"] = aliases
    return write_frontmatter(fm, body)


def collapse_doubled(inner: Path, apply: bool) -> list[dict]:
    """Move all files from inner up to inner.parent. Inner is e.g. Leads/Leads."""
    moves = []
    outer = inner.parent
    for child in sorted(inner.iterdir()):
        dst = outer / child.name
        if dst.exists():
            moves.append({"action": "collapse_skip_collision", "src": str(child.relative_to(VAULT)), "dst": str(dst.relative_to(VAULT))})
            continue
        moves.append({"action": "collapse_move", "src": str(child.relative_to(VAULT)), "dst": str(dst.relative_to(VAULT))})
        if apply:
            shutil.move(str(child), str(dst))
    if apply:
        try:
            inner.rmdir()
            moves.append({"action": "collapse_rmdir", "path": str(inner.relative_to(VAULT))})
        except OSError as e:
            moves.append({"action": "collapse_rmdir_failed", "path": str(inner.relative_to(VAULT)), "error": str(e)})
    return moves


def rename_to_index(src: Path, apply: bool) -> dict | None:
    """Rename Folder/Folder.md -> Folder/_index.md and add alias."""
    folder = src.parent
    dst = folder / "_index.md"
    if dst.exists():
        return {"action": "rename_skip_exists", "src": str(src.relative_to(VAULT)), "dst": str(dst.relative_to(VAULT))}
    alias = src.stem
    entry = {"action": "rename_to_index", "src": str(src.relative_to(VAULT)), "dst": str(dst.relative_to(VAULT)), "alias": alias}
    if apply:
        text = src.read_text(encoding="utf-8")
        new_text = add_alias(text, alias)
        dst.write_text(new_text, encoding="utf-8")
        src.unlink()
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Execute moves; default is dry run")
    ap.add_argument("--only", choices=["collapse", "rename"], help="Run only one phase")
    args = ap.parse_args()

    run_ts = datetime.now(timezone.utc).isoformat()
    log({"action": "run_start", "ts": run_ts, "apply": args.apply, "only": args.only})

    summary = {"collapses": 0, "renames": 0, "skips": 0}

    if args.only != "rename":
        print("== Phase 1: collapse doubled folders ==")
        doubled = find_doubled_folders(VAULT)
        for inner in doubled:
            print(f"  collapsing: {inner.relative_to(VAULT)}")
            entries = collapse_doubled(inner, args.apply)
            for e in entries:
                e["ts"] = run_ts
                log(e)
                if "skip" in e["action"] or "failed" in e["action"]:
                    summary["skips"] += 1
                else:
                    summary["collapses"] += 1

    if args.only != "collapse":
        print("== Phase 2: rename parent-named indexes ==")
        indexes = find_parent_named_indexes(VAULT)
        for src in indexes:
            print(f"  rename: {src.relative_to(VAULT)} -> _index.md")
            entry = rename_to_index(src, args.apply)
            if entry is None:
                continue
            entry["ts"] = run_ts
            log(entry)
            if "skip" in entry["action"]:
                summary["skips"] += 1
            else:
                summary["renames"] += 1

    log({"action": "run_end", "ts": run_ts, "summary": summary})
    print(f"\nSummary: {summary}")
    if not args.apply:
        print("(dry run — pass --apply to execute)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Apply stage of the Notion migration pipeline.

Reads _meta/notion-decisions.jsonl (produced by Claude after reviewing the
harvest stream) and applies the moves. Each decision is one JSON object:

  {
    "id":          "n00042",                  # matches harvest id
    "src":         "Some Notion Folder/Note.md",  # path relative to Notion/
    "dest":        "My Stuff/ideas/local-concierge.md",  # path relative to vault root
    "tags":        ["idea", "ai"],            # written to frontmatter (optional)
    "project":     "615io",                   # frontmatter (optional)
    "status":      "archived",                # frontmatter (optional)
    "drop":        false                      # if true, file is moved to _archive/notion-discarded/
  }

Modes:
  --dry-run    show planned actions, do nothing
  --apply      perform moves
  --limit N    only process first N decisions

Every applied action is appended to _meta/notion-migration.log with a
timestamp, source SHA1, and outcome so the migration is auditable and
reversible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parents[2]
NOTION_DIR = VAULT_ROOT / "Notion"
DECISIONS_FILE = VAULT_ROOT / "_meta" / "notion-decisions.jsonl"
DISCARD_DIR = VAULT_ROOT / "_archive" / "notion-discarded"
LOG_FILE = VAULT_ROOT / "_meta" / "notion-migration.log"

NOTION_UUID_PATTERNS = [
    re.compile(r"\s+[0-9a-f]{32}(?=\.[A-Za-z0-9]+$|$)", re.IGNORECASE),
    re.compile(
        r"\s+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\.[A-Za-z0-9]+$|$)",
        re.IGNORECASE,
    ),
]


def strip_notion_uuid(name: str) -> str:
    cleaned = name
    for pat in NOTION_UUID_PATTERNS:
        cleaned = pat.sub("", cleaned)
    return cleaned.strip()


def sanitize_path(rel: str) -> str:
    parts = [strip_notion_uuid(p) for p in Path(rel).parts]
    return str(Path(*parts)) if parts else rel


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def add_frontmatter(dest: Path, decision: dict) -> None:
    body = dest.read_text(encoding="utf-8", errors="replace")

    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end != -1:
            existing_block = body[4:end].strip()
            after = body[end + 4 :]
            if after.startswith("\n"):
                after = after[1:]
            if not existing_block:
                body = after
            else:
                return

    fm_lines = ["---"]
    fm_lines.append(f"created: {time.strftime('%Y-%m-%d')}")
    fm_lines.append("source: notion-archive")
    if decision.get("tags"):
        tags = ", ".join(decision["tags"])
        fm_lines.append(f"tags: [{tags}]")
    if decision.get("project"):
        fm_lines.append(f"project: {decision['project']}")
    if decision.get("status"):
        fm_lines.append(f"status: {decision['status']}")
    fm_lines.append("---")
    fm_lines.append("")
    dest.write_text("\n".join(fm_lines) + body, encoding="utf-8")


def apply_one(decision: dict, dry: bool, log_fh) -> str:
    src = NOTION_DIR / decision["src"]
    if not src.exists():
        return f"MISS {decision['id']} {decision['src']}"

    if decision.get("drop"):
        dest = DISCARD_DIR / sanitize_path(decision["src"])
    else:
        dest = VAULT_ROOT / sanitize_path(decision["dest"])

    if dest.exists():
        # Disambiguate
        i = 2
        stem = dest.stem
        while dest.exists():
            dest = dest.with_name(f"{stem} ({i}){dest.suffix}")
            i += 1

    digest = sha1(src)
    line = (
        f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\t{decision['id']}\t"
        f"{digest}\t{decision['src']}\t→\t{dest.relative_to(VAULT_ROOT)}"
    )

    if dry:
        print(f"DRY  {line}")
        return "DRY"

    dest.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dest)
    if not decision.get("drop"):
        add_frontmatter(dest, decision)
    log_fh.write(line + "\n")
    log_fh.flush()
    print(f"MOVE {line}")
    return "OK"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply", file=sys.stderr)
        return 2

    if not DECISIONS_FILE.exists():
        print(f"No decisions file at {DECISIONS_FILE}", file=sys.stderr)
        return 1

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_mode = "a" if args.apply else "w"
    n = 0
    with LOG_FILE.open(log_mode, encoding="utf-8") as log_fh:
        if args.apply:
            log_fh.write(f"# session start {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        with DECISIONS_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                decision = json.loads(line)
                apply_one(decision, dry=args.dry_run, log_fh=log_fh)
                n += 1
                if args.limit and n >= args.limit:
                    break
    print(f"\nProcessed {n} decisions ({'dry-run' if args.dry_run else 'applied'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

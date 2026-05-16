#!/usr/bin/env python3
"""
Clean Notion-export artifacts from path components in the vault.

Removes leading emojis, normalizes em/en dashes to hyphens, and replaces
ampersands/plus signs with "and" in folder and file names under:
  My Stuff/, Banyan Labs/, The Rehearsal/, _archive/

Skips Notion/ and Attachments/ (those layers are either being deleted or are
read-only). Logs every rename to _meta/path-cleanup.log.

Run with --dry-run or --apply.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = VAULT_ROOT / "_meta" / "path-cleanup.log"

TARGET_ROOTS = ["My Stuff", "Banyan Labs", "The Rehearsal", "_archive"]
SKIP_ROOTS = {"Notion", "Attachments", "_meta", ".claude", ".obsidian", "Daily"}

EMOJI_RANGES = [
    (0x1F300, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x1F000, 0x1F2FF),
    (0x1F900, 0x1F9FF),
]


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in EMOJI_RANGES)


def clean_component(name: str) -> str:
    out = name
    while out and (is_emoji(out[0]) or out[0] in " \t"):
        out = out[1:]
    out = out.replace("–", "-").replace("—", "-")
    out = re.sub(r"\s+\+\s+", " and ", out)
    out = re.sub(r"\s+&\s+", " and ", out)
    out = unicodedata.normalize("NFC", out)
    return out.strip()


def collect_renames(root: Path) -> list[tuple[Path, Path]]:
    renames: list[tuple[Path, Path]] = []
    all_dirs = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for d in all_dirs:
        clean = clean_component(d.name)
        if clean and clean != d.name:
            renames.append((d, d.with_name(clean)))
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        clean = clean_component(f.name)
        if clean and clean != f.name:
            renames.append((f, f.with_name(clean)))
    return renames


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply", file=sys.stderr)
        return 2

    all_renames: list[tuple[Path, Path]] = []
    for top in TARGET_ROOTS:
        root = VAULT_ROOT / top
        if not root.exists():
            continue
        all_renames.extend(collect_renames(root))

    print(f"{'Would rename' if args.dry_run else 'Renaming'} {len(all_renames)} paths")
    for old, new in all_renames:
        rel_old = old.relative_to(VAULT_ROOT)
        rel_new = new.relative_to(VAULT_ROOT)
        print(f"  {rel_old}  →  {rel_new}")

    if args.dry_run:
        return 0

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log_fh:
        log_fh.write(f"# session {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        for old, new in all_renames:
            if not old.exists():
                continue
            if new.exists():
                continue
            shutil.move(str(old), str(new))
            log_fh.write(f"{old.relative_to(VAULT_ROOT)}\t→\t{new.relative_to(VAULT_ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

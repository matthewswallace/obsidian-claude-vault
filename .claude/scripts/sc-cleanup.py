#!/usr/bin/env python3
"""
Remove stale Smart Connections embeddings — .ajson files whose source note no
longer exists. Forces SC to re-embed new files on next Obsidian launch.

Reversible: copies removed files to .smart-env/multi-stale-YYYYMMDD/ instead of deleting.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
INDEX_DIR = VAULT / ".smart-env" / "multi"


def parse_paths(ajson_file: Path) -> list[str]:
    """Return list of note paths referenced in this .ajson file."""
    try:
        raw = ajson_file.read_text(encoding="utf-8").rstrip().rstrip(",")
        data = json.loads("{" + raw + "}")
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    for k, v in data.items():
        if isinstance(v, dict) and v.get("path"):
            out.append(v["path"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not INDEX_DIR.exists():
        print("no .smart-env/multi/ found", )
        return

    stale_dir = VAULT / ".smart-env" / f"multi-stale-{datetime.now().strftime('%Y%m%d')}"

    stale_files = []
    total = 0
    for f in INDEX_DIR.glob("*.ajson"):
        total += 1
        paths = parse_paths(f)
        if not paths:
            continue
        # File is stale if NONE of its referenced paths exist
        if not any((VAULT / p).exists() for p in paths):
            stale_files.append(f)

    print(f"Scanned {total} .ajson files")
    print(f"Stale (source notes gone): {len(stale_files)}")

    if not args.apply:
        for f in stale_files[:10]:
            print(f"  would remove: {f.name}")
        if len(stale_files) > 10:
            print(f"  ... and {len(stale_files) - 10} more")
        print("\n(dry run — pass --apply to move to multi-stale-* backup)")
        return

    stale_dir.mkdir(parents=True, exist_ok=True)
    for f in stale_files:
        shutil.move(str(f), str(stale_dir / f.name))
    print(f"Moved {len(stale_files)} stale files to {stale_dir.relative_to(VAULT)}")
    print("Open Obsidian and let Smart Connections re-embed new/moved notes (may take a few minutes).")


if __name__ == "__main__":
    main()

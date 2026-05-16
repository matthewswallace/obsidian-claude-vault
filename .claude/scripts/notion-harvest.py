#!/usr/bin/env python3
"""
Harvest stage of the Notion migration pipeline.

Reads every .md file under Notion/, emits two artifacts:
  _meta/notion-harvest.jsonl  — one JSON object per non-stub, non-vant4ge file:
      {id, path, size, mtime, bucket_hint, head}
  _meta/notion-stubs.list     — paths of files ≤32 bytes (delete candidates).

Vant4ge-suspect files are written to _meta/notion-vant4ge-review.jsonl for
human review and never enter the migration stream.

Re-uses the classifier from notion-analyzer.py for bucket hints. Run again any
time the archive changes; output is fully regenerated.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from notion_analyzer import classify, peek  # noqa: E402

VAULT_ROOT = Path(__file__).resolve().parents[2]
NOTION_DIR = VAULT_ROOT / "Notion"
HARVEST_OUT = VAULT_ROOT / "_meta" / "notion-harvest.jsonl"
STUBS_OUT = VAULT_ROOT / "_meta" / "notion-stubs.list"
VANT4GE_OUT = VAULT_ROOT / "_meta" / "notion-vant4ge-review.jsonl"

HEAD_BYTES = 800
STUB_MAX_BYTES = 32


def main() -> int:
    if not NOTION_DIR.exists():
        print(f"Notion dir not found: {NOTION_DIR}", file=sys.stderr)
        return 1

    HARVEST_OUT.parent.mkdir(parents=True, exist_ok=True)

    n_total = n_harvest = n_stub = n_vant = 0
    with HARVEST_OUT.open("w", encoding="utf-8") as fh_harv, \
         STUBS_OUT.open("w", encoding="utf-8") as fh_stub, \
         VANT4GE_OUT.open("w", encoding="utf-8") as fh_vant:
        for dirpath, _dirnames, filenames in os.walk(NOTION_DIR):
            for fname in filenames:
                if not fname.lower().endswith(".md"):
                    continue
                fpath = Path(dirpath) / fname
                try:
                    st = fpath.stat()
                except OSError:
                    continue
                n_total += 1
                rel = str(fpath.relative_to(NOTION_DIR))
                content = peek(fpath)
                bucket, _signals = classify(fpath, st.st_size, content)

                row = {
                    "id": f"n{n_total:05d}",
                    "path": rel,
                    "size": st.st_size,
                    "mtime": int(st.st_mtime),
                    "bucket_hint": bucket,
                    "head": content[:HEAD_BYTES],
                }

                if bucket == "vant4ge-suspect":
                    fh_vant.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n_vant += 1
                elif bucket == "stub-garbage":
                    fh_stub.write(f"{rel}\t{st.st_size}\n")
                    n_stub += 1
                else:
                    fh_harv.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n_harvest += 1

    print(f"Harvest complete: {n_total} files scanned")
    print(f"  → harvest stream: {n_harvest} ({HARVEST_OUT.name})")
    print(f"  → stubs list:     {n_stub}   ({STUBS_OUT.name})")
    print(f"  → vant4ge review: {n_vant}   ({VANT4GE_OUT.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Retrofit frontmatter on files that have already been migrated but were
written before the empty-frontmatter-stripping fix landed in notion-apply.py.

Reads _meta/notion-decisions.jsonl + _meta/notion-migration.log to figure out
which files moved where, then re-applies the (improved) add_frontmatter logic
in-place. Idempotent — skips files that already have a non-empty frontmatter
block.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

VAULT_ROOT = Path(__file__).resolve().parents[2]
DECISIONS = VAULT_ROOT / "_meta" / "notion-decisions.jsonl"
LOG = VAULT_ROOT / "_meta" / "notion-migration.log"


def retrofit_one(dest: Path, decision: dict) -> str:
    body = dest.read_text(encoding="utf-8", errors="replace")
    needs_new = False

    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end != -1:
            existing_block = body[4:end].strip()
            after = body[end + 4 :]
            if after.startswith("\n"):
                after = after[1:]
            if not existing_block:
                body = after
                needs_new = True
            else:
                return "skip-has-fm"
        else:
            return "skip-malformed"
    else:
        needs_new = True

    if not needs_new:
        return "skip"

    fm_lines = ["---"]
    fm_lines.append(f"created: {time.strftime('%Y-%m-%d')}")
    fm_lines.append("source: notion-archive")
    if decision.get("tags"):
        fm_lines.append(f"tags: [{', '.join(decision['tags'])}]")
    if decision.get("project"):
        fm_lines.append(f"project: {decision['project']}")
    if decision.get("status"):
        fm_lines.append(f"status: {decision['status']}")
    fm_lines.append("---")
    fm_lines.append("")
    dest.write_text("\n".join(fm_lines) + body, encoding="utf-8")
    return "ok"


def main() -> int:
    decisions_by_id: dict[str, dict] = {}
    with DECISIONS.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            d = json.loads(line)
            decisions_by_id[d["id"]] = d

    counts: dict[str, int] = {}
    with LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            ts, did, _sha, _src, _arrow, dest_rel = parts
            decision = decisions_by_id.get(did)
            if not decision or decision.get("drop"):
                continue
            dest_path = VAULT_ROOT / dest_rel
            if not dest_path.exists():
                counts["missing"] = counts.get("missing", 0) + 1
                continue
            outcome = retrofit_one(dest_path, decision)
            counts[outcome] = counts.get(outcome, 0) + 1

    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

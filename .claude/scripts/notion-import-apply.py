#!/usr/bin/env python3
"""
Apply moves from _meta/notion-import-plan.jsonl.

Dry-run by default. --apply commits. Logs to _meta/notion-import-cleanup.log (JSONL).
After all moves succeed, removes empty notion-import/ trees.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_config import find_vault_root, load_config, folder

VAULT = find_vault_root()
CFG = load_config()
META = VAULT / folder(CFG, "meta", "_meta")
PLAN = META / "notion-import-plan.jsonl"
LOG = META / "notion-import-cleanup.log"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def log_op(rec):
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="commit (default dry-run)")
    args = ap.parse_args()

    if not PLAN.exists():
        print(f"No plan at {PLAN}. Run notion-import-plan.py first.", file=sys.stderr)
        sys.exit(2)

    rows = [json.loads(l) for l in PLAN.read_text().splitlines() if l.strip()]
    moves = [r for r in rows if r.get("status") == "ok"]
    print(f"{'APPLYING' if args.apply else 'DRY-RUN'}: {len(moves)} moves")

    moved = 0
    for r in moves:
        src = VAULT / r["src"]
        dst = VAULT / r["dst"]
        if not src.exists():
            print(f"  SKIP missing: {r['src']}")
            continue
        if dst.exists():
            print(f"  SKIP collision: {r['src']} → {r['dst']}")
            continue
        if args.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                src_sha = sha(src)
            except Exception:
                src_sha = None
            src.rename(dst)
            log_op({
                "ts": time.strftime("%FT%T%z"),
                "op": "move",
                "src": r["src"],
                "dst": r["dst"],
                "sha": src_sha,
            })
            moved += 1
        else:
            print(f"  would: {r['src']}\n       → {r['dst']}")

    if args.apply:
        # Remove empty directories in notion-import/ trees
        roots = [
            VAULT / "Banyan Labs/notion-import",
            VAULT / "The Rehearsal/notion-import",
        ]
        removed_dirs = 0
        for root in roots:
            if not root.exists():
                continue
            # Remove from deepest to shallowest
            for p in sorted(root.rglob("*"), key=lambda x: -len(x.parts)):
                if p.is_dir():
                    try:
                        p.rmdir()
                        removed_dirs += 1
                    except OSError:
                        pass
            try:
                root.rmdir()
                removed_dirs += 1
                log_op({"ts": time.strftime("%FT%T%z"), "op": "rmdir", "src": str(root.relative_to(VAULT))})
            except OSError:
                print(f"  notion-import/ at {root.relative_to(VAULT)} not empty — leaving in place")

        print(f"\nMoved {moved} files. Removed {removed_dirs} empty directories.")
    else:
        print(f"\n{len(moves)} moves would happen. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()

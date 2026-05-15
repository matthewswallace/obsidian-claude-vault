#!/usr/bin/env python3
"""
Apply rename / move suggestions from _meta/triage-renames.jsonl and _meta/triage-moves.jsonl.

Dry-run is default. --apply commits. All operations log to _meta/triage-apply.log
(JSONL with timestamp + sha + from + to) for full reversibility.

Usage:
  python3 .claude/scripts/triage-apply.py --renames               # dry-run renames
  python3 .claude/scripts/triage-apply.py --renames --apply       # commit renames
  python3 .claude/scripts/triage-apply.py --moves --cluster "recipes"     # dry-run one cluster
  python3 .claude/scripts/triage-apply.py --moves --cluster "recipes" --apply
  python3 .claude/scripts/triage-apply.py --min-score 5 --moves   # only apply moves with score >= 5
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_config import load_config, find_vault_root, folder

_cfg = load_config()
VAULT = find_vault_root()
META = VAULT / folder(_cfg, "meta", "_meta")
RENAMES = META / "triage-renames.jsonl"
MOVES = META / "triage-moves.jsonl"
LOG = META / "triage-apply.log"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def log(op, src, dst, dry):
    rec = {
        "ts": time.strftime("%FT%T%z"),
        "op": op,
        "src": str(src.relative_to(VAULT)),
        "dst": str(dst.relative_to(VAULT)) if dst else None,
        "sha": sha(src) if src.exists() else None,
        "dry": dry,
    }
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def apply_renames(min_severity, apply):
    if not RENAMES.exists():
        print("No renames file. Run triage-themes.py first.")
        return
    rows = [json.loads(l) for l in RENAMES.read_text().splitlines() if l.strip()]
    # Only "genuine" issues, not just "long"
    genuine_issues = {"uuid", "hex-tail", "emoji", "punct-heavy"}
    if min_severity == "genuine":
        rows = [r for r in rows if any(i in r["issues"] for i in genuine_issues)]
    print(f"{'APPLYING' if apply else 'DRY-RUN'}: {len(rows)} renames")
    for r in rows:
        src = VAULT / r["from"]
        if not src.exists():
            continue
        new_name = r["stem_clean"] + ".md"
        dst = src.parent / new_name
        if dst.exists() and dst != src:
            print(f"  SKIP collision: {src.name} → {new_name}")
            continue
        print(f"  {'→' if apply else 'would'}: {src.name}")
        print(f"      → {new_name}")
        if apply and src != dst:
            log("rename", src, dst, dry=False)
            src.rename(dst)
        else:
            log("rename", src, dst, dry=True)


def apply_moves(cluster_filter, min_score, apply):
    if not MOVES.exists():
        print("No moves file. Run triage-themes.py first.")
        return
    rows = [json.loads(l) for l in MOVES.read_text().splitlines() if l.strip()]
    if cluster_filter:
        rows = [r for r in rows if r["target"] == cluster_filter]
    rows = [r for r in rows if r["score"] >= min_score]
    print(f"{'APPLYING' if apply else 'DRY-RUN'}: {len(rows)} moves (cluster={cluster_filter or 'all'}, min_score={min_score})")
    for r in rows:
        src = VAULT / r["from"]
        if not src.exists():
            continue
        target_dir = VAULT / r["target"]
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / src.name
        if dst.exists() and dst != src:
            print(f"  SKIP collision: {src.relative_to(VAULT)} → {dst.relative_to(VAULT)}")
            continue
        print(f"  {'→' if apply else 'would'}: {src.relative_to(VAULT)}")
        print(f"      → {dst.relative_to(VAULT)} (score {r['score']})")
        if apply:
            log("move", src, dst, dry=False)
            src.rename(dst)
        else:
            log("move", src, dst, dry=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renames", action="store_true", help="apply rename suggestions")
    ap.add_argument("--moves", action="store_true", help="apply move suggestions")
    ap.add_argument("--cluster", help="limit moves to one target folder")
    ap.add_argument("--min-score", type=int, default=5, help="minimum cluster score (default 5)")
    ap.add_argument("--min-severity", choices=["all", "genuine"], default="genuine",
                    help="rename severity: 'all' (incl. long-only) or 'genuine' (uuid/hex/emoji/punct only)")
    ap.add_argument("--apply", action="store_true", help="actually do it (default is dry-run)")
    args = ap.parse_args()

    if not (args.renames or args.moves):
        ap.error("specify --renames or --moves")

    if args.renames:
        apply_renames(args.min_severity, args.apply)
    if args.moves:
        apply_moves(args.cluster, args.min_score, args.apply)


if __name__ == "__main__":
    main()

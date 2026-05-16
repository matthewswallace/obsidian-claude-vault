#!/usr/bin/env python3
"""
Smart Connections CLI — query cached embeddings from outside Obsidian.

Reads .smart-env/multi/*.ajson (one per note), builds in-memory similarity index,
and returns nearest neighbors for a given note path.

No model inference: only works for notes already embedded by Smart Connections.
For ad-hoc text queries, add an embedding model (e.g. ollama pull nomic-embed-text).

Usage:
    sc-query.py related <note-path>        Top neighbors for a note (path relative to vault)
    sc-query.py related <path> --limit 10
    sc-query.py related <path> --json
    sc-query.py stats                      Index stats
    sc-query.py orphans                    Notes with NO strong neighbors (similarity < 0.3 to all)
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Iterable

VAULT = Path(__file__).resolve().parents[2]
INDEX_DIR = VAULT / ".smart-env" / "multi"
EMBED_KEY = "TaylorAI/bge-micro-v2"


def load_index(only_sources: bool = True) -> dict[str, list[float]]:
    """Return {path: vec}. Only smart_sources entries (full notes), not blocks."""
    out = {}
    for f in INDEX_DIR.glob("*.ajson"):
        try:
            # ajson is a JSON fragment shaped like: "key": {...},
            # Wrap as {"$body": ...} to parse
            raw = f.read_text(encoding="utf-8").rstrip().rstrip(",")
            wrapped = "{" + raw + "}"
            data = json.loads(wrapped)
        except (json.JSONDecodeError, OSError):
            continue
        for k, v in data.items():
            if only_sources and not k.startswith("smart_sources:"):
                continue
            if not isinstance(v, dict):
                continue
            path = v.get("path") or k.split(":", 1)[1]
            embs = v.get("embeddings", {})
            model_data = embs.get(EMBED_KEY) or next(iter(embs.values()), None)
            if not model_data or not model_data.get("vec"):
                continue
            out[path] = model_data["vec"]
    return out


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(sum(x * x for x in a))


def cosine(a, b):
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def find_path(index: dict, query: str) -> str | None:
    """Resolve a query path to an index key (allows partial / basename match)."""
    if query in index:
        return query
    # Try exact basename match
    for k in index:
        if Path(k).name == Path(query).name:
            return k
    # Substring match — return first
    for k in index:
        if query.lower() in k.lower():
            return k
    return None


def cmd_related(args):
    index = load_index()
    key = find_path(index, args.note)
    if key is None:
        print(f"note not found in index: {args.note}", file=sys.stderr)
        print(f"(index has {len(index)} notes)", file=sys.stderr)
        sys.exit(1)
    qvec = index[key]
    scored = []
    for path, vec in index.items():
        if path == key:
            continue
        s = cosine(qvec, vec)
        scored.append((s, path))
    scored.sort(reverse=True)
    top = scored[: args.limit]
    if args.json:
        print(json.dumps({"query": key, "neighbors": [{"score": s, "path": p} for s, p in top]}, indent=2))
    else:
        print(f"# Related to: {key}\n")
        for s, p in top:
            print(f"- {s:.3f}  [[{Path(p).stem}]]  `{p}`")


def cmd_stats(args):
    index = load_index()
    print(f"Indexed notes: {len(index)}")
    if index:
        sample_vec = next(iter(index.values()))
        print(f"Embedding dims: {len(sample_vec)}")
        print(f"Embed model: {EMBED_KEY}")
    by_folder = {}
    for p in index:
        top = p.split("/", 1)[0]
        by_folder[top] = by_folder.get(top, 0) + 1
    print("\nBy top-level folder:")
    for k, v in sorted(by_folder.items(), key=lambda kv: -kv[1]):
        print(f"  {k:40} {v}")


def cmd_orphans(args):
    """Find notes whose best neighbor scores below threshold (semantic isolates)."""
    index = load_index()
    items = list(index.items())
    threshold = args.threshold
    orphans = []
    for i, (path, vec) in enumerate(items):
        best = 0.0
        for j, (_, other) in enumerate(items):
            if i == j:
                continue
            s = cosine(vec, other)
            if s > best:
                best = s
                if best >= threshold:
                    break
        if best < threshold:
            orphans.append((best, path))
        if i % 500 == 0 and i:
            print(f"  scanned {i}/{len(items)}...", file=sys.stderr)
    orphans.sort()
    print(f"# Orphans (best neighbor < {threshold})\n")
    for s, p in orphans[: args.limit]:
        print(f"- {s:.3f}  `{p}`")
    print(f"\nTotal: {len(orphans)} of {len(items)}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rel = sub.add_parser("related", help="Find notes similar to a given note")
    p_rel.add_argument("note")
    p_rel.add_argument("--limit", type=int, default=15)
    p_rel.add_argument("--json", action="store_true")
    p_rel.set_defaults(func=cmd_related)

    p_stats = sub.add_parser("stats")
    p_stats.set_defaults(func=cmd_stats)

    p_orph = sub.add_parser("orphans")
    p_orph.add_argument("--threshold", type=float, default=0.5)
    p_orph.add_argument("--limit", type=int, default=50)
    p_orph.set_defaults(func=cmd_orphans)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

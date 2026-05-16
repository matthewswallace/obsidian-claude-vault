#!/usr/bin/env python3
"""
Map-of-Content (MOC) generator.

Given a topic folder, scans for notes (in-folder + cross-folder matches via
keyword), groups by sub-folder, and writes a curated _MOC.md.

Usage:
    make-moc.py "Banyan Labs"
    make-moc.py "My Stuff/personal" --keywords personal,life
    make-moc.py "Banyan Labs/projects/AIDA" --keywords aida --apply
    make-moc.py "Banyan Labs" --dry          # default — print to stdout

The generated MOC is a STARTING POINT, not final. User is expected to curate.

Structure:
    # <Topic> — Map of Content
    > Generated 2026-05-16. Curate as needed.
    ## Indexes
    - [[_index]] notes from each sub-folder
    ## Notes by sub-folder
    ### <subfolder>
    - [[Note]]
    ## Related semantic neighbors (top 10 from sc-query)
    - [[Note]]  (0.78)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

VAULT = Path(__file__).resolve().parents[2]
SC_QUERY = VAULT / ".claude/scripts/sc-query.py"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def fm(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        d = yaml.safe_load(m.group(1)) or {}
        return d if isinstance(d, dict) else {}
    except yaml.YAMLError:
        return {}


def is_index(path: Path) -> bool:
    return path.name == "_index.md"


def display_link(path: Path) -> str:
    """[[Folder]] for _index.md (via alias), [[stem]] otherwise."""
    if is_index(path):
        return f"[[{path.parent.name}]]"
    return f"[[{path.stem}]]"


def walk_folder(folder: Path) -> dict[str, list[Path]]:
    """Group notes by sub-folder relative to folder."""
    groups: dict[str, list[Path]] = {}
    for p in sorted(folder.rglob("*.md")):
        if any(part.startswith(".") for part in p.parts):
            continue
        rel = p.relative_to(folder)
        sub = str(rel.parent) if str(rel.parent) != "." else "(root)"
        groups.setdefault(sub, []).append(p)
    return groups


def semantic_neighbors(folder_index: Path, limit: int) -> list[tuple[float, str]]:
    """Get top neighbors of folder's _index.md via sc-query if it exists."""
    if not folder_index.exists():
        return []
    rel = str(folder_index.relative_to(VAULT))
    try:
        out = subprocess.run(
            ["python3", str(SC_QUERY), "related", rel, "--limit", str(limit), "--json"],
            capture_output=True, text=True, check=True, cwd=str(VAULT),
        )
    except subprocess.CalledProcessError:
        return []
    data = json.loads(out.stdout)
    return [(n["score"], n["path"]) for n in data.get("neighbors", [])]


def keyword_matches(folder: Path, keywords: list[str], excluded: set[Path]) -> list[Path]:
    """Find notes outside `folder` whose path or tags match any keyword."""
    if not keywords:
        return []
    pat = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    hits = []
    for p in VAULT.rglob("*.md"):
        if any(part.startswith(".") for part in p.parts):
            continue
        if p in excluded:
            continue
        try:
            if folder in p.parents:
                continue
        except ValueError:
            pass
        rel_str = str(p.relative_to(VAULT))
        if pat.search(rel_str):
            hits.append(p)
            continue
        meta = fm(p)
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        if any(pat.search(str(t)) for t in tags):
            hits.append(p)
    return sorted(hits)[:30]  # cap


def build_moc(folder: Path, keywords: list[str], neighbors_limit: int) -> str:
    title = folder.name
    groups = walk_folder(folder)
    folder_index = folder / "_index.md"
    in_folder = {p for ps in groups.values() for p in ps}

    lines = []
    lines.append(f"---")
    lines.append(f"created: {date.today().isoformat()}")
    lines.append(f"tags: [moc]")
    lines.append(f"status: active")
    lines.append(f"---\n")
    lines.append(f"# {title} — Map of Content")
    lines.append(f"\n> Generated {date.today().isoformat()} by `make-moc.py`. Curate as needed.\n")

    # Indexes (every _index.md in tree)
    indexes = [p for ps in groups.values() for p in ps if is_index(p)]
    if indexes:
        lines.append("## Folder indexes\n")
        for p in sorted(indexes, key=lambda x: str(x.relative_to(folder))):
            depth = len(p.relative_to(folder).parts) - 1
            indent = "  " * max(0, depth - 1)
            lines.append(f"{indent}- {display_link(p)}  `{p.relative_to(VAULT)}`")
        lines.append("")

    # Notes by sub-folder
    lines.append("## Notes by sub-folder\n")
    for sub in sorted(groups.keys()):
        non_idx = [p for p in groups[sub] if not is_index(p)]
        if not non_idx:
            continue
        lines.append(f"### {sub}\n")
        for p in sorted(non_idx):
            lines.append(f"- {display_link(p)}")
        lines.append("")

    # Cross-folder keyword matches
    if keywords:
        hits = keyword_matches(folder, keywords, in_folder)
        if hits:
            lines.append(f"## Cross-folder matches (keywords: {', '.join(keywords)})\n")
            for p in hits:
                lines.append(f"- {display_link(p)}  `{p.relative_to(VAULT)}`")
            lines.append("")

    # Semantic neighbors of folder index
    if folder_index.exists():
        nbrs = semantic_neighbors(folder_index, neighbors_limit)
        # filter: skip those already in-folder
        nbrs = [(s, p) for s, p in nbrs if (VAULT / p) not in in_folder]
        if nbrs:
            lines.append(f"## Semantic neighbors of `{title}/_index.md`\n")
            for score, p in nbrs:
                lines.append(f"- {score:.3f}  [[{Path(p).parent.name if Path(p).name == '_index.md' else Path(p).stem}]]  `{p}`")
            lines.append("")

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--keywords", default="", help="Comma-separated keywords for cross-folder match")
    ap.add_argument("--neighbors", type=int, default=10)
    ap.add_argument("--apply", action="store_true", help="Write to <folder>/_MOC.md; default dumps to stdout")
    args = ap.parse_args()

    folder = (VAULT / args.folder).resolve()
    if not folder.is_dir():
        print(f"not a folder: {folder}", file=sys.stderr)
        sys.exit(1)
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    content = build_moc(folder, keywords, args.neighbors)

    if args.apply:
        out = folder / "_MOC.md"
        if out.exists():
            print(f"_MOC.md exists, skipping (delete first to regen): {out.relative_to(VAULT)}", file=sys.stderr)
            sys.exit(1)
        out.write_text(content, encoding="utf-8")
        print(f"wrote {out.relative_to(VAULT)} ({len(content.splitlines())} lines)")
    else:
        print(content)


if __name__ == "__main__":
    main()

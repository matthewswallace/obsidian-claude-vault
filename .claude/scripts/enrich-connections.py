#!/usr/bin/env python3
"""
Enrich a note's frontmatter with semantic neighbors from Smart Connections.

For each target note:
  1. Query sc-query.py for top-K neighbors above min-score
  2. Skip self, skip neighbors whose wikilink already appears in body
  3. Add to `related:` frontmatter list (deduped)
  4. Log to _meta/enrich.log

Usage:
  enrich-connections.py path "Banyan Labs/Banyan Labs Vision and Mission Summary.md"
  enrich-connections.py recent --days 7
  enrich-connections.py folder "My Stuff/personal"
  enrich-connections.py path "<note>" --apply       # default is dry run
  enrich-connections.py path "<note>" --limit 5 --min-score 0.7
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

VAULT = Path(__file__).resolve().parents[2]
LOG = VAULT / "_meta" / "enrich.log"
SC_QUERY = VAULT / ".claude/scripts/sc-query.py"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")


def parse_frontmatter(raw: str) -> dict:
    if yaml:
        try:
            fm = yaml.safe_load(raw) or {}
            return fm if isinstance(fm, dict) else {}
        except yaml.YAMLError:
            return {}

    fm = {}
    current_key = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_key:
            fm.setdefault(current_key, []).append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if not value:
            fm[key] = []
        elif value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
            fm[key] = [v for v in items if v]
        else:
            fm[key] = value.strip('"').strip("'")
    return fm


def dump_frontmatter(fm: dict) -> str:
    if yaml:
        return yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip()

    lines = []
    for key, value in fm.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif value is None:
            lines.append(f"{key}:")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_fm(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    return parse_frontmatter(m.group(1)), text[m.end():]


def write_fm(fm: dict, body: str) -> str:
    if not fm:
        return body
    dumped = dump_frontmatter(fm)
    return f"---\n{dumped}\n---\n{body}"


def existing_wikilinks(body: str) -> set[str]:
    return {m.group(1).strip() for m in WIKILINK_RE.finditer(body)}


def get_neighbors(note_rel: str, limit: int) -> list[tuple[float, str]]:
    """Call sc-query.py and parse JSON output."""
    try:
        out = subprocess.run(
            ["python3", str(SC_QUERY), "related", note_rel, "--limit", str(limit), "--json"],
            capture_output=True, text=True, check=True, cwd=str(VAULT),
        )
    except subprocess.CalledProcessError as e:
        print(f"  sc-query failed for {note_rel}: {e.stderr.strip()}", file=sys.stderr)
        return []
    data = json.loads(out.stdout)
    return [(n["score"], n["path"]) for n in data.get("neighbors", [])]


def enrich_one(note: Path, limit: int, min_score: float, apply: bool) -> dict:
    rel = str(note.relative_to(VAULT))
    text = note.read_text(encoding="utf-8")
    fm, body = read_fm(text)

    neighbors = get_neighbors(rel, limit=limit * 3)  # over-fetch to filter
    if not neighbors:
        return {"path": rel, "added": [], "skipped_reason": "no_neighbors"}

    existing_links = existing_wikilinks(body)
    existing_related = fm.get("related") or []
    if isinstance(existing_related, str):
        existing_related = [existing_related]

    additions = []
    for score, npath in neighbors:
        if score < min_score:
            break  # neighbors are sorted desc
        p = Path(npath)
        # _index.md is non-unique — use parent folder name (matches the alias added in Stage 1)
        display = p.parent.name if p.stem == "_index" else p.stem
        wikilink = f"[[{display}]]"
        if display in existing_links:
            continue
        if wikilink in existing_related:
            continue
        additions.append((round(score, 3), display, wikilink, npath))
        if len(additions) >= limit:
            break

    if not additions:
        return {"path": rel, "added": [], "skipped_reason": "no_new"}

    new_related = list(existing_related) + [a[2] for a in additions]
    fm["related"] = new_related
    new_text = write_fm(fm, body)

    entry = {
        "path": rel,
        "added": [{"score": a[0], "wikilink": a[2], "target": a[3]} for a in additions],
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if apply:
        note.write_text(new_text, encoding="utf-8")
        log(entry)
    return entry


def select_notes(args) -> list[Path]:
    if args.cmd == "path":
        return [VAULT / args.note]
    if args.cmd == "folder":
        folder = VAULT / args.folder
        return sorted(p for p in folder.rglob("*.md") if "_archive" not in p.parts)
    if args.cmd == "recent":
        cutoff = time.time() - args.days * 86400
        out = []
        for p in VAULT.rglob("*.md"):
            if any(part.startswith(".") or part in ("_archive", "Attachments") for part in p.parts):
                continue
            if p.stat().st_mtime > cutoff:
                out.append(p)
        return sorted(out, key=lambda p: -p.stat().st_mtime)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--limit", type=int, default=5, help="Max neighbors to add per note")
    common.add_argument("--min-score", type=float, default=0.6, help="Skip neighbors below this cosine score")
    common.add_argument("--apply", action="store_true", help="Write changes; default is dry run")

    p = sub.add_parser("path", parents=[common]); p.add_argument("note")
    p = sub.add_parser("folder", parents=[common]); p.add_argument("folder")
    p = sub.add_parser("recent", parents=[common]); p.add_argument("--days", type=int, default=7)

    args = ap.parse_args()
    notes = select_notes(args)
    if not notes:
        print("no matching notes", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(notes)} note(s) — limit={args.limit}, min_score={args.min_score}, apply={args.apply}")
    total_added = 0
    for note in notes:
        if not note.exists():
            print(f"  skip (missing): {note.relative_to(VAULT)}")
            continue
        entry = enrich_one(note, args.limit, args.min_score, args.apply)
        if entry["added"]:
            print(f"  {note.relative_to(VAULT)}: +{len(entry['added'])} related")
            for a in entry["added"]:
                print(f"     {a['score']:.3f}  {a['wikilink']}  ({a['target']})")
            total_added += len(entry["added"])

    print(f"\nTotal added: {total_added}{' (dry run)' if not args.apply else ''}")


if __name__ == "__main__":
    main()

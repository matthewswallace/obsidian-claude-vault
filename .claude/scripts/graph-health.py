#!/usr/bin/env python3
"""
Graph-health report. Audits vault as a connected graph and surfaces:

  - Orphans       — notes with no inbound wikilinks AND no related: frontmatter
  - Dense hubs    — top-N most-linked-to notes (MOC candidates)
  - Stale         — notes still tagged 'needs-triage' or status:needs-triage
  - Untagged      — notes with no tags: frontmatter
  - Recent        — top-10 most-recently-modified

Writes report to _meta/graph-health-YYYY-WW.md. Designed to be invoked manually
or by the weekly-graph-health schedule routine (which mails the report).
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

VAULT = Path(__file__).resolve().parents[2]
SKIP_PARTS = {".obsidian", ".claude", ".git", "_archive", "Attachments", "_meta", ".smart-env", "node_modules", ".trash"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+?)(?:[#\|][^\]]*)?\]\]")


def is_in_scope(p: Path) -> bool:
    return not any(part in SKIP_PARTS for part in p.parts)


def read_note(p: Path) -> tuple[dict, str]:
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
        if not isinstance(meta, dict):
            meta = {}
    except yaml.YAMLError:
        meta = {}
    return meta, text[m.end():]


def is_needs_triage(meta: dict) -> bool:
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if "needs-triage" in tags:
        return True
    if meta.get("status") == "needs-triage":
        return True
    return False


def collect():
    notes = []
    for p in VAULT.rglob("*.md"):
        if not is_in_scope(p):
            continue
        meta, body = read_note(p)
        wl = {m.group(1).strip() for m in WIKILINK_RE.finditer(body)}
        related = meta.get("related") or []
        if isinstance(related, str):
            related = [related]
        related_targets = {WIKILINK_RE.match(r).group(1).strip() if WIKILINK_RE.match(r) else r for r in related}
        notes.append({
            "path": str(p.relative_to(VAULT)),
            "stem": p.stem,
            "folder_name": p.parent.name,
            "is_index": p.name == "_index.md",
            "meta": meta,
            "wikilinks_out": wl | related_targets,
            "tags": meta.get("tags") or [],
            "status": meta.get("status"),
            "mtime": p.stat().st_mtime,
        })

    # Build alias map: stem (or folder_name for _index.md) -> path
    alias_map = {}
    for n in notes:
        key = n["folder_name"] if n["is_index"] else n["stem"]
        alias_map.setdefault(key, []).append(n["path"])
        # Also map any frontmatter aliases
        ali = n["meta"].get("aliases") or []
        if isinstance(ali, str):
            ali = [ali]
        for a in ali:
            alias_map.setdefault(str(a), []).append(n["path"])

    # Build inbound count
    inbound = Counter()
    inbound_from = defaultdict(set)
    for n in notes:
        for target in n["wikilinks_out"]:
            for resolved in alias_map.get(target, []):
                if resolved == n["path"]:
                    continue
                inbound[resolved] += 1
                inbound_from[resolved].add(n["path"])

    return notes, inbound, inbound_from


def report(args):
    notes, inbound, _inbound_from = collect()
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()

    orphans = []
    for n in notes:
        if n["is_index"]:
            continue
        has_out = bool(n["wikilinks_out"])
        has_in = inbound.get(n["path"], 0) > 0
        if not has_out and not has_in:
            orphans.append(n)

    hubs = sorted(inbound.items(), key=lambda kv: -kv[1])[: args.hubs_top]
    stale = [n for n in notes if is_needs_triage(n["meta"])]
    untagged = [n for n in notes if not n["tags"]]
    recent = sorted(notes, key=lambda n: -n["mtime"])[: args.recent_top]

    cutoff_recent = datetime.now(timezone.utc).timestamp() - 7 * 86400
    last_week = [n for n in notes if n["mtime"] > cutoff_recent]

    lines = []
    lines.append("---")
    lines.append(f"created: {today.isoformat()}")
    lines.append(f"tags: [meta, graph-health]")
    lines.append("---\n")
    lines.append(f"# Graph health — {iso_year}-W{iso_week:02d}\n")
    lines.append(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by `graph-health.py`._\n")
    lines.append(f"**Totals**: {len(notes)} notes · {len(orphans)} orphans · {sum(inbound.values())} inbound links · {len(stale)} stale · {len(untagged)} untagged · {len(last_week)} modified in last 7 days\n")

    # Dense hubs
    lines.append("## Densest hubs (MOC candidates)\n")
    if hubs:
        for path, count in hubs:
            stem = Path(path).stem if Path(path).name != "_index.md" else Path(path).parent.name
            lines.append(f"- **{count}** inbound — [[{stem}]]  `{path}`")
    else:
        lines.append("_(no inbound links — vault has very sparse linking)_")
    lines.append("")

    # Orphans
    lines.append(f"## Orphans ({len(orphans)})\n")
    lines.append("Notes with no outbound wikilinks AND no inbound references. Candidates for deletion, enrichment, or MOC inclusion.\n")
    for n in orphans[: args.orphans_top]:
        lines.append(f"- [[{n['stem']}]]  `{n['path']}`")
    if len(orphans) > args.orphans_top:
        lines.append(f"- ... and {len(orphans) - args.orphans_top} more")
    lines.append("")

    # Stale needs-triage
    lines.append(f"## Stale `needs-triage` ({len(stale)})\n")
    for n in stale[:30]:
        lines.append(f"- [[{n['stem']}]]  `{n['path']}`")
    if len(stale) > 30:
        lines.append(f"- ... and {len(stale) - 30} more")
    lines.append("")

    # Untagged
    lines.append(f"## Untagged notes ({len(untagged)})\n")
    for n in untagged[:30]:
        lines.append(f"- [[{n['stem']}]]  `{n['path']}`")
    if len(untagged) > 30:
        lines.append(f"- ... and {len(untagged) - 30} more")
    lines.append("")

    # Recent
    lines.append(f"## Recently modified ({len(last_week)} in last 7 days)\n")
    for n in last_week[:20]:
        dt = datetime.fromtimestamp(n["mtime"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"- `{dt}` [[{n['stem']}]]  `{n['path']}`")
    lines.append("")

    output = "\n".join(lines) + "\n"

    if args.stdout:
        print(output)
    else:
        out_path = VAULT / "_meta" / f"graph-health-{iso_year}-W{iso_week:02d}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"wrote {out_path.relative_to(VAULT)} ({len(notes)} notes audited)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orphans-top", type=int, default=30)
    ap.add_argument("--hubs-top", type=int, default=15)
    ap.add_argument("--recent-top", type=int, default=20)
    ap.add_argument("--stdout", action="store_true", help="Print to stdout instead of writing _meta/ file")
    report(ap.parse_args())


if __name__ == "__main__":
    main()

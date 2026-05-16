#!/usr/bin/env python3
"""
Notion archive analyzer.

Walks Notion/ recursively, classifies each markdown file by filename + content
heuristics, and emits _meta/notion-classification.md for user review.

Output buckets:
  stub-garbage       — 9-byte (or near-empty) Notion stub files
  notion-timestamp   — auto-named like 2025-09-16T115800.000-0500.md
  journal-day        — Nth.md (1st, 2nd, ..., 31st)
  project-task       — "1.1.1 Foo.md" / "2.3 Bar.md" hierarchical task notes
  recipe             — food/cooking content
  music              — band, gig, setlist, Nashville, music career
  work-history       — career narrative, Gun.io, resume material
  vant4ge-suspect    — anything that name-drops Vant4ge / employer
  ai-product-idea    — app/product idea, firebase, MVP, build plan
  meeting-notes      — retrospective, standup, meeting
  reference          — privacy policy, terms, contracts
  personal           — anxiety, depression, reflection, journal-like
  unknown            — couldn't classify confidently

Heuristics are intentionally conservative — false negatives push files to
"unknown" rather than misfile them.
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parents[2]
NOTION_DIR = VAULT_ROOT / "Notion"
OUT_FILE = VAULT_ROOT / "_meta" / "notion-classification.md"

PEEK_BYTES = 600
STUB_MAX_BYTES = 32

JOURNAL_DAY_RE = re.compile(r"^\d{1,2}(st|nd|rd|th)\.md$", re.IGNORECASE)
NOTION_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{6}\.\d{3}[+-]\d{4}\.md$")
PROJECT_TASK_RE = re.compile(r"^\d+(\.\d+){1,3}\s+\S.+\.md$")

VANT4GE_TERMS = re.compile(r"\bvant4ge\b|\bvantage\b", re.IGNORECASE)

RECIPE_TERMS = re.compile(
    r"\b(ingredient|teaspoon|tablespoon|cup|preheat|bake|sauté|recipe|"
    r"olive oil|garlic|onion|chicken|salt and pepper)\b",
    re.IGNORECASE,
)
MUSIC_TERMS = re.compile(
    r"\b(setlist|chord|gig|nashville|songwriter|verse|chorus|bridge|"
    r"rehearsal|band|guitar|bpm|capo|key of [a-g])\b",
    re.IGNORECASE,
)
WORK_HISTORY_TERMS = re.compile(
    r"\b(gun\.io|resume|career|hiring manager|cover letter|"
    r"my experience at|years of experience|portfolio|references)\b",
    re.IGNORECASE,
)
AI_PRODUCT_TERMS = re.compile(
    r"\b(firebase|firestore|mvp|user stor(y|ies)|api endpoint|"
    r"app idea|product idea|build (a |an )|stripe|auth flow)\b",
    re.IGNORECASE,
)
MEETING_TERMS = re.compile(
    r"\b(retrospective|standup|sprint|meeting notes|action items|"
    r"attendees|agenda)\b",
    re.IGNORECASE,
)
REFERENCE_TERMS = re.compile(
    r"\b(privacy policy|terms of service|terms and conditions|"
    r"contract|nda|non-disclosure)\b",
    re.IGNORECASE,
)
PERSONAL_TERMS = re.compile(
    r"\b(anxiety|depression|reflection|gratitude|journal|"
    r"feelings|therapy|self-care|year-end)\b",
    re.IGNORECASE,
)


def peek(path: Path) -> str:
    try:
        with path.open("rb") as fh:
            raw = fh.read(PEEK_BYTES)
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def classify(path: Path, size: int, content: str) -> tuple[str, list[str]]:
    """Return (primary_bucket, signal_list). Signals show why."""
    name = path.name
    signals: list[str] = []

    if VANT4GE_TERMS.search(content) or VANT4GE_TERMS.search(name):
        signals.append("vant4ge-term")
        return "vant4ge-suspect", signals

    if size <= STUB_MAX_BYTES:
        signals.append(f"size<={STUB_MAX_BYTES}b")
        return "stub-garbage", signals

    if NOTION_TS_RE.match(name):
        signals.append("notion-timestamp-name")
        return "notion-timestamp", signals

    if JOURNAL_DAY_RE.match(name):
        signals.append("Nth.md name")
        return "journal-day", signals

    if PROJECT_TASK_RE.match(name):
        signals.append("hierarchical-task-name")
        return "project-task", signals

    scores: Counter[str] = Counter()
    for bucket, regex in [
        ("recipe", RECIPE_TERMS),
        ("music", MUSIC_TERMS),
        ("work-history", WORK_HISTORY_TERMS),
        ("ai-product-idea", AI_PRODUCT_TERMS),
        ("meeting-notes", MEETING_TERMS),
        ("reference", REFERENCE_TERMS),
        ("personal", PERSONAL_TERMS),
    ]:
        hits = regex.findall(content)
        if hits:
            scores[bucket] = len(hits)
            signals.append(f"{bucket}:{len(hits)}")

    if scores:
        return scores.most_common(1)[0][0], signals

    return "unknown", signals


def first_line(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return ""


def walk_notion() -> list[dict]:
    rows = []
    for dirpath, _dirnames, filenames in os.walk(NOTION_DIR):
        for fname in filenames:
            if not fname.lower().endswith(".md"):
                continue
            fpath = Path(dirpath) / fname
            try:
                st = fpath.stat()
            except OSError:
                continue
            content = peek(fpath)
            bucket, signals = classify(fpath, st.st_size, content)
            rows.append(
                {
                    "rel": str(fpath.relative_to(NOTION_DIR)),
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
                    "bucket": bucket,
                    "signals": ",".join(signals) if signals else "",
                    "first": first_line(content),
                }
            )
    return rows


def write_report(rows: list[dict]) -> None:
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_bucket[r["bucket"]].append(r)

    bucket_order = [
        "vant4ge-suspect",
        "unknown",
        "stub-garbage",
        "notion-timestamp",
        "journal-day",
        "project-task",
        "ai-product-idea",
        "music",
        "work-history",
        "recipe",
        "meeting-notes",
        "reference",
        "personal",
    ]

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as fh:
        fh.write("---\n")
        fh.write(f"created: {datetime.now().strftime('%Y-%m-%d')}\n")
        fh.write("tags: [meta, notion-import]\n")
        fh.write("status: awaiting-review\n")
        fh.write("---\n\n")
        fh.write("# Notion Archive Classification\n\n")
        fh.write(
            f"Total markdown files scanned: **{len(rows)}**. "
            "Review each bucket and tell Claude the target folder + any per-file overrides.\n\n"
        )

        fh.write("## Bucket summary\n\n")
        fh.write("| bucket | count | total size |\n|---|---:|---:|\n")
        for b in bucket_order:
            items = by_bucket.get(b, [])
            if not items:
                continue
            total_kb = sum(i["size"] for i in items) // 1024
            fh.write(f"| {b} | {len(items)} | {total_kb} KB |\n")
        leftovers = set(by_bucket) - set(bucket_order)
        for b in sorted(leftovers):
            items = by_bucket[b]
            total_kb = sum(i["size"] for i in items) // 1024
            fh.write(f"| {b} | {len(items)} | {total_kb} KB |\n")
        fh.write("\n")

        fh.write("## Suggested target folders (Claude's recs — edit before migration)\n\n")
        fh.write(
            "- `vant4ge-suspect` → manual review one-by-one. Do NOT auto-route.\n"
            "- `unknown` → manual review; likely splits into personal/music/ai-product/_Inbox.\n"
            "- `stub-garbage` → delete after spot-check.\n"
            "- `notion-timestamp` → `_Inbox/from-notion/` for later sift.\n"
            "- `journal-day` → `Daily/legacy/` (renamed with year context if recoverable).\n"
            "- `project-task` → group by parent project: probably `Banyan Labs/legacy/` or `_archive/projects/`.\n"
            "- `ai-product-idea` → `My Stuff/ideas/`.\n"
            "- `music` → `The Rehearsal/legacy/`.\n"
            "- `work-history` → `My Stuff/career/` (NON-Vant4ge).\n"
            "- `recipe` → `My Stuff/recipes/`.\n"
            "- `meeting-notes` → archive by project, else `_archive/meetings/`.\n"
            "- `reference` → `_archive/reference/`.\n"
            "- `personal` → `My Stuff/personal/`.\n\n"
        )

        for b in bucket_order:
            items = by_bucket.get(b, [])
            if not items:
                continue
            fh.write(f"## {b} ({len(items)})\n\n")
            items_sorted = sorted(items, key=lambda r: (-r["size"], r["rel"]))
            limit = 40 if b in {"stub-garbage", "notion-timestamp", "journal-day"} else 200
            shown = items_sorted[:limit]
            fh.write("| file | size | mtime | signals | first line |\n")
            fh.write("|---|---:|---|---|---|\n")
            for r in shown:
                first = r["first"].replace("|", "\\|")
                fh.write(
                    f"| `{r['rel']}` | {r['size']} | {r['mtime']} | "
                    f"{r['signals']} | {first} |\n"
                )
            if len(items_sorted) > limit:
                fh.write(f"\n_...{len(items_sorted) - limit} more in this bucket (truncated)._\n")
            fh.write("\n")

        for b in sorted(leftovers):
            items = by_bucket[b]
            fh.write(f"## {b} ({len(items)})\n\n")
            for r in sorted(items, key=lambda r: r["rel"])[:50]:
                first = r["first"].replace("|", "\\|")
                fh.write(f"- `{r['rel']}` ({r['size']}b) — {first}\n")
            fh.write("\n")


def main() -> int:
    if not NOTION_DIR.exists():
        print(f"Notion dir not found: {NOTION_DIR}", file=sys.stderr)
        return 1
    rows = walk_notion()
    write_report(rows)
    print(f"Wrote {OUT_FILE} ({len(rows)} files classified)")
    counts = Counter(r["bucket"] for r in rows)
    for b, c in counts.most_common():
        print(f"  {b}: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

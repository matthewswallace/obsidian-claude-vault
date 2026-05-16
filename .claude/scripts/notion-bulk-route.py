#!/usr/bin/env python3
"""
Bulk router for the Notion migration. Applies folder-level rules to every
harvest entry not yet present in _meta/notion-decisions.jsonl and appends new
decisions.

Rules are evaluated top-down; first match wins. Each rule is a dict with:
  match:    folder prefix relative to Notion/ (e.g. "Habit Tracker/")
            "" matches root-level files
  dest:     destination folder relative to vault root, OR
  drop:     true to send to _archive/notion-discarded/
  tags:     list of tag strings written to frontmatter
  project:  optional project frontmatter
  status:   optional status frontmatter
  rename:   "preserve" (default) or "flatten" (strip parent path)

Output is appended (not overwritten) so prior batches stay in the log.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parents[2]
HARVEST = VAULT_ROOT / "_meta" / "notion-harvest.jsonl"
DECISIONS = VAULT_ROOT / "_meta" / "notion-decisions.jsonl"

RULES: list[dict] = [
    # ---- Drop piles (lowest-value first so they short-circuit) ----
    {"match": "Habit Tracker/", "drop": True, "tags": ["habit-tracker"]},
    {"match": "Untitled Database/", "drop": True, "tags": ["notion-default"]},
    {"match": "Todo Lists/", "drop": True, "tags": ["old-todo"]},
    {"match": "To-Do/", "drop": True, "tags": ["old-todo"]},
    {"match": "Schedule/", "drop": True, "tags": ["old-schedule"]},
    {"match": "Schedule (1)/", "drop": True, "tags": ["old-schedule"]},
    {"match": "Retrospective (Template)/", "drop": True, "tags": ["template"]},
    {"match": "Agile Retrospective Template/", "drop": True, "tags": ["template"]},

    # ---- Cold archive (preserve for reference) ----
    {"match": "Evernote/", "dest": "_archive/evernote-import/",
     "tags": ["evernote", "archive"], "status": "archived"},
    {"match": "attachments/", "dest": "_archive/notion-attachments/",
     "tags": ["attachment", "archive"], "status": "archived"},
    {"match": "My links/", "dest": "_archive/links/",
     "tags": ["links", "archive"], "status": "archived"},

    # ---- The Rehearsal cluster ----
    {"match": "The Rehearsal Project/", "dest": "The Rehearsal/notion-import/project/",
     "tags": ["the-rehearsal", "project"]},
    {"match": "The Rehearsal Partnership Plan/", "dest": "The Rehearsal/notion-import/partnership/",
     "tags": ["the-rehearsal", "partnership"]},
    {"match": "The Rehearsal/", "dest": "The Rehearsal/notion-import/",
     "tags": ["the-rehearsal"]},
    {"match": "The Venue + The Rehearsal/", "dest": "The Rehearsal/notion-import/venue/",
     "tags": ["the-rehearsal", "venue"]},
    {"match": "🎵 Song Catalog/", "dest": "The Rehearsal/song-catalog/",
     "tags": ["music", "song-catalog"]},
    {"match": "Song ideas/", "dest": "The Rehearsal/song-ideas/",
     "tags": ["music", "songwriting"]},
    {"match": "Lyrics/", "dest": "The Rehearsal/lyrics/",
     "tags": ["music", "lyrics"]},

    # ---- Banyan Labs ----
    {"match": "Banyan Labs/", "dest": "Banyan Labs/notion-import/",
     "tags": ["banyan"], "project": "banyan"},
    {"match": "Procure Path MVP and Long-Term Roadmap/",
     "dest": "Banyan Labs/projects/ProcurePath/",
     "tags": ["banyan", "procurepath", "project"], "project": "banyan"},
    {"match": "SOWs/", "dest": "Banyan Labs/SOWs/",
     "tags": ["banyan", "sow", "contract"], "project": "banyan"},

    # ---- Career / engineering methodology ----
    {"match": "Engineering Wiki/", "dest": "My Stuff/career/engineering-wiki/",
     "tags": ["career", "engineering", "wiki"]},
    {"match": "Engineering Coaching/", "dest": "My Stuff/career/coaching/",
     "tags": ["career", "coaching"]},
    {"match": "Engineering Strategist and Coaching/",
     "dest": "My Stuff/career/strategist-coaching/",
     "tags": ["career", "strategy", "coaching"]},
    {"match": "Software Engineering Framework/",
     "dest": "My Stuff/career/methodology/",
     "tags": ["career", "methodology", "framework"]},
    {"match": "Delivery Framework/", "dest": "My Stuff/career/methodology/",
     "tags": ["career", "delivery", "methodology"]},
    {"match": "Delivery Assurance and Engineering Processes/",
     "dest": "My Stuff/career/methodology/",
     "tags": ["career", "delivery", "qa", "methodology"]},
    {"match": "Proposal for Director of Mentorship and President-CTO/",
     "dest": "My Stuff/career/proposals/",
     "tags": ["career", "proposal", "leadership"]},
    {"match": "Matthew Wallace – Personal & Professional Summary/",
     "dest": "My Stuff/career/summary/",
     "tags": ["career", "summary"]},

    # ---- Client / external project work ----
    {"match": "ODE Project Management/", "dest": "My Stuff/clients/ODE/",
     "tags": ["client", "ode", "project-mgmt"]},
    {"match": "ODE Steering 700 Modernization/", "dest": "My Stuff/clients/ODE/",
     "tags": ["client", "ode", "steering700", "modernization"]},

    # ---- Product / app ideas ----
    {"match": "FitRoute Walk & Workout/", "dest": "My Stuff/ideas/FitRoute/",
     "tags": ["idea", "app", "fitness"]},
    {"match": "Anchor The Men's App for Real Growth/", "dest": "My Stuff/ideas/Anchor/",
     "tags": ["idea", "app"]},
    {"match": "Pixtreme concept/", "dest": "My Stuff/ideas/Pixtreme/",
     "tags": ["idea", "video", "saas"]},
    {"match": "Venueblast Board/", "dest": "My Stuff/ideas/Venueblast/",
     "tags": ["idea", "venueblast"]},
    {"match": "Venueblast/", "dest": "My Stuff/ideas/Venueblast/",
     "tags": ["idea", "venueblast"]},
    {"match": "Flip it open/", "dest": "My Stuff/ideas/FlipItOpen/",
     "tags": ["idea"]},
    {"match": "Flutter App/", "dest": "My Stuff/ideas/Flutter-App/",
     "tags": ["idea", "flutter"]},
    {"match": "FractionalEdge/", "dest": "My Stuff/ideas/FractionalEdge/",
     "tags": ["idea", "fractional"]},
    {"match": "Solutions Briefs/", "dest": "My Stuff/ideas/solutions-briefs/",
     "tags": ["idea", "solutions-brief"]},
    {"match": "Mailbox money/", "dest": "My Stuff/ideas/Mailbox-Money/",
     "tags": ["idea", "income"]},
    {"match": "idea drawer/", "dest": "My Stuff/ideas/drawer/",
     "tags": ["idea", "drawer"]},
    {"match": "615io Projects/", "dest": "My Stuff/615io/",
     "tags": ["615io"]},
    {"match": "Pixtreme concept/", "dest": "My Stuff/ideas/Pixtreme/",
     "tags": ["idea", "pixtreme"]},

    # ---- Writing ----
    {"match": "LinkedIn posts/", "dest": "My Stuff/writing/linkedin/",
     "tags": ["writing", "linkedin"]},
    {"match": "Weekly newsletter/", "dest": "My Stuff/writing/newsletter/",
     "tags": ["writing", "newsletter"]},
    {"match": "Writing/", "dest": "My Stuff/writing/",
     "tags": ["writing"]},

    # ---- Personal ----
    {"match": "Personal Home/", "dest": "My Stuff/personal/",
     "tags": ["personal"]},
    {"match": "Anxiety and depression/", "dest": "My Stuff/personal/health/",
     "tags": ["personal", "mental-health"]},
    {"match": "Jesus Answer/", "dest": "My Stuff/bible-study/",
     "tags": ["bible-study", "faith"]},
    {"match": "Overlanding/", "dest": "My Stuff/personal/overlanding/",
     "tags": ["personal", "overlanding"]},
    {"match": "🤝 Connections Tracker/", "dest": "My Stuff/personal/connections/",
     "tags": ["personal", "relationships", "network"]},
    {"match": "Resume Improvement Recommendations for Devin Wallace/",
     "dest": "My Stuff/personal/family/devin-resume/",
     "tags": ["personal", "family", "devin"]},

    # ---- Travel ----
    {"match": "All-in-One Travel Planner/", "dest": "My Stuff/travel/",
     "tags": ["travel"]},

    # ---- Learning ----
    {"match": "Learning/", "dest": "My Stuff/learning/",
     "tags": ["learning"]},

    # ---- The Personal-Work folder is mixed — route to ideas inbox for now ----
    {"match": "Personal work/", "dest": "My Stuff/personal-work-inbox/",
     "tags": ["personal-work", "needs-triage"], "status": "needs-triage"},

    # ---- mswallace's notebook = Notion default capture page, deeply mixed ----
    {"match": "mswallace's notebook/", "dest": "_archive/notebook-import/",
     "tags": ["notebook", "needs-triage"], "status": "needs-triage"},

    # ---- General / catch-all ambiguous ----
    {"match": "General/", "dest": "_archive/notion-general/",
     "tags": ["general", "needs-triage"], "status": "needs-triage"},
]


def existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                d = json.loads(line)
                ids.add(d["id"])
            except Exception:
                continue
    return ids


def find_rule(rel_path: str) -> dict | None:
    for rule in RULES:
        m = rule["match"]
        if not m:
            if "/" not in rel_path:
                return rule
            continue
        if rel_path.startswith(m):
            return rule
    return None


def dest_for(rule: dict, src_rel: str) -> str:
    if rule.get("drop"):
        return ""
    base = rule["dest"]
    src_path = Path(src_rel)
    filename = src_path.name
    parent_under_match = (
        str(src_path.parent)[len(rule["match"].rstrip("/")) + 1 :]
        if rule["match"] and str(src_path.parent).startswith(rule["match"].rstrip("/"))
        else ""
    )
    if rule.get("rename") == "flatten" or not parent_under_match:
        return str(Path(base) / filename)
    return str(Path(base) / parent_under_match / filename)


def main() -> int:
    done = existing_ids(DECISIONS)
    appended = 0
    skipped_existing = 0
    unmatched: list[str] = []

    with HARVEST.open(encoding="utf-8") as fh_in, \
         DECISIONS.open("a", encoding="utf-8") as fh_out:
        fh_out.write(f"# bulk-route batch — {Path(__file__).name}\n")
        for line in fh_in:
            row = json.loads(line)
            if row["id"] in done:
                skipped_existing += 1
                continue
            rule = find_rule(row["path"])
            if not rule:
                unmatched.append(row["path"])
                continue
            decision = {"id": row["id"], "src": row["path"]}
            if rule.get("drop"):
                decision["drop"] = True
            else:
                decision["dest"] = dest_for(rule, row["path"])
            if rule.get("tags"):
                decision["tags"] = rule["tags"]
            if rule.get("project"):
                decision["project"] = rule["project"]
            if rule.get("status"):
                decision["status"] = rule["status"]
            fh_out.write(json.dumps(decision, ensure_ascii=False) + "\n")
            appended += 1

    print(f"Appended {appended} new decisions to {DECISIONS.name}")
    print(f"Skipped {skipped_existing} already-decided entries")
    print(f"Unmatched (no rule applies): {len(unmatched)}")
    if unmatched[:20]:
        print("First 20 unmatched paths:")
        for p in unmatched[:20]:
            print(f"  - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

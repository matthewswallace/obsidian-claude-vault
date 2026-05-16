#!/usr/bin/env python3
"""
Plan moves out of Banyan Labs/notion-import/ and The Rehearsal/notion-import/
into clean sibling folders. Outputs _meta/notion-import-plan.jsonl and a readable
table at _meta/notion-import-plan.md.

Read-only. Does not move anything. Apply separately with notion-import-apply.py.
"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_config import find_vault_root, load_config, folder

VAULT = find_vault_root()
CFG = load_config()
META = VAULT / folder(CFG, "meta", "_meta")

# Mapping: prefix (relative to vault) → target folder
# Order matters: most-specific first.
MAPPINGS = [
    # Banyan Labs dashboard → operations or root
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Banyan Todo Board",        "Banyan Labs/operations/todo"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Tasks Tracker",            "Banyan Labs/operations/tasks"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Weekly Scorecard",         "Banyan Labs/operations/scorecard"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Retrospectives",           "Banyan Labs/operations/retros"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Operations",               "Banyan Labs/operations"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Leads",                    "Banyan Labs/leads"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Banyan Labs Projects",     "Banyan Labs/projects"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard/Proposals",                "Banyan Labs/proposals"),
    ("Banyan Labs/notion-import/Banyan Labs - Dashboard",                          "Banyan Labs/operations/dashboard"),
    # Banyan Labs top-level subfolders
    ("Banyan Labs/notion-import/Meeting Notes",                                    "Banyan Labs/meeting-notes"),
    ("Banyan Labs/notion-import/Proposals",                                        "Banyan Labs/proposals"),
    ("Banyan Labs/notion-import/Ideas",                                            "Banyan Labs/ideas"),
    ("Banyan Labs/notion-import/People/Interviews",                                "Banyan Labs/people/interviews"),
    ("Banyan Labs/notion-import/People",                                           "Banyan Labs/people"),
    ("Banyan Labs/notion-import/Areas of Business Focus/Services Based Work",      "Banyan Labs/business-focus/services"),
    ("Banyan Labs/notion-import/Areas of Business Focus/Apps",                     "Banyan Labs/business-focus/apps"),
    ("Banyan Labs/notion-import/Areas of Business Focus/SaaS and Products",        "Banyan Labs/business-focus/saas"),
    ("Banyan Labs/notion-import/Areas of Business Focus",                          "Banyan Labs/business-focus"),
    # Banyan Labs root-level files (just filename, no subdir)
    ("Banyan Labs/notion-import",                                                  "Banyan Labs"),

    # The Rehearsal
    ("The Rehearsal/notion-import/project/User Stories",                           "The Rehearsal/project/user-stories"),
    ("The Rehearsal/notion-import/project/Features",                               "The Rehearsal/project/features"),
    ("The Rehearsal/notion-import/project",                                        "The Rehearsal/project"),
    ("The Rehearsal/notion-import/venue/Venue Name Options",                       "The Rehearsal/venues/name-options"),
    ("The Rehearsal/notion-import/venue",                                          "The Rehearsal/venues"),
    ("The Rehearsal/notion-import/partnership",                                    "The Rehearsal/partnership"),
    ("The Rehearsal/notion-import",                                                "The Rehearsal"),
]


def plan_moves():
    plans = []
    counter = Counter()

    notion_import_roots = [
        VAULT / "Banyan Labs/notion-import",
        VAULT / "The Rehearsal/notion-import",
    ]

    all_files = []
    for r in notion_import_roots:
        if r.exists():
            all_files.extend(r.rglob("*.md"))

    for f in all_files:
        rel = str(f.relative_to(VAULT))
        target_dir = None
        for prefix, target in MAPPINGS:
            if rel.startswith(prefix + "/") or rel == prefix:
                # remove the prefix, keep the remainder
                remainder = rel[len(prefix):].lstrip("/")
                # remainder might be deeper subpath (e.g. "Operations/foo/bar.md")
                # but our MAPPINGS handle each common depth, so remainder is typically just filename
                target_dir = target
                # Strip trailing subdir components from remainder if any (shouldn't happen with current mapping)
                target_path = (VAULT / target / remainder)
                break
        if target_dir is None:
            # No mapping → leave alone, flag
            plans.append({"src": rel, "dst": None, "status": "no-mapping"})
            counter["no-mapping"] += 1
            continue

        # Detect collision
        target_rel = str(target_path.relative_to(VAULT))
        if target_path.exists():
            plans.append({"src": rel, "dst": target_rel, "status": "collision"})
            counter["collision"] += 1
        else:
            plans.append({"src": rel, "dst": target_rel, "status": "ok"})
            counter["ok"] += 1

    return plans, counter


def write_outputs(plans, counter):
    META.mkdir(parents=True, exist_ok=True)
    jsonl_path = META / "notion-import-plan.jsonl"
    md_path = META / "notion-import-plan.md"

    with jsonl_path.open("w") as f:
        for p in plans:
            f.write(json.dumps(p) + "\n")

    lines = [
        "---",
        "purpose: notion-import/ subfolder merge plan",
        "generated: 2026-05-15",
        "status: review",
        "---",
        "",
        "# notion-import/ cleanup plan",
        "",
        f"**Total files:** {sum(counter.values())}",
        f"**Ready to move (no collision):** {counter['ok']}",
        f"**Collisions (need decision):** {counter['collision']}",
        f"**No mapping (left in place):** {counter['no-mapping']}",
        "",
        "## Moves by target folder",
        "",
    ]
    # Group by destination parent folder for readability
    by_dst = {}
    for p in plans:
        if not p["dst"]:
            continue
        # parent folder of dst
        parts = p["dst"].split("/")
        bucket = "/".join(parts[:-1])
        by_dst.setdefault(bucket, []).append(p)

    for bucket in sorted(by_dst):
        rows = by_dst[bucket]
        lines.append(f"### → `{bucket}/` ({len(rows)} files)")
        lines.append("")
        for p in rows[:30]:
            status_icon = "⚠" if p["status"] == "collision" else "→"
            lines.append(f"- {status_icon} `{p['src']}`")
        if len(rows) > 30:
            lines.append(f"- _...{len(rows)-30} more_")
        lines.append("")

    if counter["collision"] > 0:
        lines += [
            "## Collisions",
            "",
            "These files would overwrite existing notes. Resolution: append `(notion)` suffix to source filename before move.",
            "",
        ]
        for p in plans:
            if p["status"] == "collision":
                lines.append(f"- `{p['src']}` → would clobber `{p['dst']}`")

    if counter["no-mapping"] > 0:
        lines += [
            "",
            "## Unmapped (left in place)",
            "",
        ]
        for p in plans:
            if p["status"] == "no-mapping":
                lines.append(f"- `{p['src']}`")

    md_path.write_text("\n".join(lines))
    print(f"Wrote {jsonl_path.relative_to(VAULT)}")
    print(f"Wrote {md_path.relative_to(VAULT)}")
    print(f"Counters: {dict(counter)}")


if __name__ == "__main__":
    plans, counter = plan_moves()
    write_outputs(plans, counter)

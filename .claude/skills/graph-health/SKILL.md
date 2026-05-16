---
name: graph-health
description: Audit the vault as a connected graph. Reports orphans, densest hubs (MOC candidates), stale 'needs-triage' notes, untagged notes, and recent activity. Use when user says "graph health", "vault audit", "find orphans", "/graph-health", or on the weekly schedule.
---

# Graph health audit

Runs `.claude/scripts/graph-health.py` to produce a weekly snapshot of the vault's connectedness. Output written to `_meta/graph-health-YYYY-WW.md`.

## When to invoke

- User says: "graph health", "vault audit", "find orphans", "what should I link", "/graph-health"
- Saturday morning (paired with weekly-review)
- After large content imports

## What it produces

A markdown report with five sections:

1. **Densest hubs** — top-N most-linked-to notes. High inbound = de-facto MOC candidate.
2. **Orphans** — notes with no outbound wikilinks AND no inbound references. Either delete, enrich, or absorb into a MOC.
3. **Stale `needs-triage`** — anything still flagged needs-triage after past triage runs.
4. **Untagged** — notes with no `tags:` frontmatter. Untagged → invisible to Dataview.
5. **Recently modified** — last 7 days of edits.

## CLI

```bash
python3 .claude/scripts/graph-health.py                    # writes _meta/graph-health-YYYY-WW.md
python3 .claude/scripts/graph-health.py --stdout           # print to console
python3 .claude/scripts/graph-health.py --orphans-top 50   # tune output
```

## Workflow

1. Run script (or just call it via this skill).
2. Read the generated report.
3. For top orphans: run `enrich-connections.py path <orphan>` to add semantic neighbors.
4. For densest hubs without a MOC: run `make-moc.py "<folder>" --apply` to create one.
5. For stale needs-triage: triage manually via `inbox-triage.py`.

## Scheduling (when user is ready)

Local launchd, weekly Saturday 09:00:

```bash
cp _meta/launchd/com.473studio.graph-health.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.473studio.graph-health.plist
# To disable later: launchctl unload -w ~/Library/LaunchAgents/com.473studio.graph-health.plist
```

The plist runs the script, which writes to the vault. Mac must be awake (or on AC + scheduled wake) at the cron time.

## Related

- [[vault-graph-architecture]] — what "graph" means here
- `make-moc.py` — generate MOC for a dense hub folder
- `enrich-connections.py` — densify orphan neighborhoods
- `weekly-review` skill — separate but complementary; this one is graph-focused

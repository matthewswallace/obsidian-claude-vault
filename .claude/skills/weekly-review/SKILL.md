---
name: weekly-review
description: Saturday roll-up of the past week. Aggregates completed tasks, daily-note highlights, top vault edits, calendar load, open project status. Writes to the configured weekly-reviews folder. Use when user says "weekly review", "wrap up the week", "week in review", "/weekly-review".
---

# Weekly Review

Saturday roll-up. Produces a single markdown note summarizing the past 7 days. Excludes the configured isolation entity by default.

## Configuration

Read `.claude/vault.json`:
- `folders.daily` — where daily notes live
- `folders.weekly_reviews` — where to write the output (default `Reviews`)
- `folders.meta` — for `captures.log`
- `isolation.folder` — folder to exclude from "top edited files" sweep
- `isolation.name` — display name for any isolation-tagged items

## When to invoke

- User says: "weekly review", "wrap up the week", "week in review", "Saturday review", "/weekly-review"
- Scheduled run via the `schedule` skill (see install instructions below)

## Output location

`{folders.weekly_reviews}/YYYY-Www.md` (ISO week number).

Example: `Reviews/2026-W20.md` for week of 2026-05-11 to 2026-05-17.

If the folder doesn't exist, create it. Filename hygiene applies.

## Data to aggregate

For the last 7 days (Sat-Sat, inclusive of generating Saturday):

1. **Daily notes** — read `{folders.daily}/YYYY-MM-DD.md` for each day; pull the `## Focus` line and any `## Notes` section.
2. **Completed ClickUp tasks** — `clickup_filter_tasks` with `status: complete`, `closed_after: 7d ago`.
3. **Top edited vault files** — `find . -mtime -7 -name "*.md"` excluding `{folders.archive}/`, `{folders.meta}/`, `.claude/`, `{isolation.folder}/` (if set); rank by edit count or just list.
4. **Calendar events done** — `list_events` past week. Count + flag any all-day or 2+ hour events.
5. **Open active projects** — grep `status: active` in frontmatter, deduped by folder.
6. **Captures logged** — tail `{folders.meta}/captures.log` for past week.

## Output template

```markdown
---
week: YYYY-Www
date_range: YYYY-MM-DD to YYYY-MM-DD
created: YYYY-MM-DD
tags: [weekly-review]
---

# Week {{Www}} — {{Mon DD}} to {{Sun DD}}

## Top of mind
{{2-3 sentence synthesis Claude writes — what stood out across the week, anchored in data below, not generic}}

## Wins / completed
{{ClickUp completed list grouped by list (project)}}

## Daily focus recap
| Day | Focus | Note |
|-----|-------|------|
{{one row per daily note with focus line}}

## Vault activity
- {{top 10 edited files, with project tag}}

## Calendar load
- {{N events, X all-day, Y meetings 2h+}}

## Active projects
- {{folder — last touched date}}

## Captures
{{captures.log entries for week, grouped by folder}}

## Carryover → next week
- [ ] {{any unfinished focus items pulled from daily notes}}
```

## Schedule install

Two options:

**Local (writes to vault directly):**
```
launchd job → python wrapper → uses obs.py REST API → writes to vault
```

**Remote (via Anthropic routines, emails draft):**
```
/schedule "weekly review every Saturday 08:00" → invoke weekly-review skill
```

Remote variant emails a draft to `user_email` from config since it can't reach the local vault.

## Caveman output to chat

5-line summary max:
```
Week {{Www}}: {{N}} tasks done. {{N}} events. Top project: {{name}}.
Top focus: {{most recurring focus theme}}.
Carryover: {{N}} items.
Written → {{folders.weekly_reviews}}/{{YYYY-Www}}.md.
```

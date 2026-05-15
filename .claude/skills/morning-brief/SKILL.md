---
name: morning-brief
description: Populate today's daily note with calendar events, unread email summary, open tasks, and recent vault activity. Respects the configured isolation entity in vault.json. Use when user says "morning brief", "start my day", "today's plan", or invokes /morning-brief.
---

# Morning Brief

Populates today's daily note. Reads: Google Calendar, Gmail (unread), open vault tasks, recent vault activity. Writes: `{daily_folder}/YYYY-MM-DD.md` where `daily_folder` comes from `.claude/vault.json` (`folders.daily`, default `Daily`).

## When to invoke

- User says: "morning brief", "what's today", "start my day", "today's plan", "/morning-brief"
- After SessionStart on a new day if user asks for orientation

## Configuration

Read `.claude/vault.json` first:
- `folders.daily` — where the daily note lives
- `isolation.name` and `isolation.folder` — the entity/folder to filter from cross-folder summaries unless explicitly scoped
- `isolation.overlap_with` — context where the isolation entity can be mentioned legitimately (e.g. client overlap)

## Steps

1. **Compute today's date** in ISO 8601 (vault uses YYYY-MM-DD).
2. **Check if `{daily_folder}/YYYY-MM-DD.md` exists**. If yes → append a `## Brief` section below existing content. If no → create with template below.
3. **Gather data in parallel** using MCP tools:
   - `mcp__claude_ai_Google_Calendar__list_events` — today only (timeMin = 00:00 local, timeMax = 24:00 local)
   - `mcp__claude_ai_Gmail__search_threads` — `is:unread newer_than:1d` (cap at 10)
   - `mcp__claude_ai_ClickUp__clickup_filter_tasks` — due today or overdue, assignee = self
   - `grep -rln "status: active" --include="*.md"` — open projects across all top-level folders EXCEPT the isolation folder (unless user explicitly scoped it in)
   - Recent vault edits (last 24h, top 5)
4. **Apply isolation filter:** drop matches from `isolation.folder` and matches against `isolation.patterns` from any cross-folder summary unless user explicitly scoped that entity in.
5. **Write the brief** using the template.
6. **Output to chat:** 5-line summary (event count, email count, task count, top focus). Caveman mode.

## Daily note template

```markdown
---
date: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
tags: [daily]
---

# {{YYYY-MM-DD}} — {{Weekday}}

## Brief
_Generated {{HH:MM}}_

### Calendar
{{events as bullets — "HH:MM–HH:MM Title" or "All day: Title"; "No events" if empty}}

### Inbox ({{N}} unread)
{{top emails as bullets — "From: Subject"; "Clean" if empty}}

### Tasks due / overdue
{{ClickUp tasks as checkboxes — "- [ ] Title (list, due)"; "None" if empty}}

### Recent vault activity
{{last 24h edits — "- `path` — title"; "Quiet" if empty}}

### Focus
_What's the one thing today?_

## Notes
```

## Caveman output style

5-line summary max. Pattern:
```
{{N}} events. Top: {{first event title}} @ {{time}}.
{{N}} unread. {{top sender if urgent}}.
{{N}} tasks due. {{top task title}}.
Recent: {{most-touched project last 24h}}.
Brief written → {{daily_folder}}/{{YYYY-MM-DD}}.md.
```

## Edge cases

- Calendar MCP fails → write brief with `_Calendar unavailable_` placeholder; continue.
- Gmail MCP fails → same pattern.
- ClickUp MCP fails → same.
- File exists with `## Brief` already today → replace that section, don't duplicate.
- Isolation-entity mentions appear in calendar/email → keep them in the brief (they're already the user's day) but tag the lines `[{{isolation.name}}]` so they're flagged. Do NOT summarize internal content beyond the calendar/email subject line itself.

## Filename hygiene

Always `{daily_folder}/YYYY-MM-DD.md`. No suffixes. No emoji.

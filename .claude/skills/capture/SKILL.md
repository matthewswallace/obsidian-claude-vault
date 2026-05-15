---
name: capture
description: Capture inbox content (text, URL, file path, dictation) and route it into the correct vault folder with clean filename + frontmatter. Respects the configured isolation entity. Use when user says "capture this", "save this", "file this", "/capture", or pastes content asking where it goes.
---

# Capture → Classify

Takes raw input → classifies → writes to correct folder with clean filename and frontmatter.

## Configuration

Read `.claude/vault.json` first:
- `isolation` — strict-isolation entity + patterns + overlap context (where it can legitimately appear)
- `project_keywords` — map of project name → regex patterns for routing
- `folders` — well-known folder slots (`inbox`, `archive`, `attachments`, etc.)
- `triage_clusters` (optional) — keyword → target folder map

## When to invoke

- User says: "capture this", "save this", "file this for me", "where should this go", "/capture"
- User pastes raw text/URL/transcript and asks for filing

## Inputs accepted

| Type | Example |
|------|---------|
| Plain text | Paste of notes, ideas, transcripts |
| URL | Article link → fetch + summarize → file |
| File path | Existing vault file to re-route |
| Title + body | Structured capture |

## Routing rules

In priority order:

1. **Explicit folder hint** ("file in <folder>") → honor exactly.
2. **Project match** via `project_keywords` from config → route to that project's folder.
3. **Isolation-entity content** detected via `isolation.patterns`:
   - If `isolation.overlap_with.context_patterns` ALSO match → route to `isolation.overlap_with.folder` (e.g. client-side mention).
   - Else → REFUSE to write and ask user to clarify scope. Never auto-write into `isolation.folder`.
4. **Triage cluster keywords** (recipe, song, travel, budget, etc.) → matching cluster folder.
5. **Idea / scratch / undecided** → `folders.inbox` (default `_inbox/` or whatever the user configured for capture overflow).
6. **External reference** (article, paper, URL) → route to a reading-list cluster if present, else `folders.archive/reference/`.

If confidence is low (< 0.7), ask user which of top-2 candidates before writing.

## Filename rules

Per [[feedback-filename-hygiene]]:
- Short, human-readable, Title Case or sentence case.
- No UUIDs, hashes, emoji.
- No redundant folder prefix (`recipes/Lasagna.md`, not `recipes/Recipe - Lasagna.md`).
- Dates only if load-bearing (events, daily notes, meeting notes).
- ≤ 60 chars.
- Collision → append a single discriminating word, not a number.

## Frontmatter template

```yaml
---
created: {{YYYY-MM-DD}}
tags: [{{auto-tag based on routing}}]
project: {{folder match if any}}
status: {{active|draft|reference|archived}}
source: {{capture | url:... | paste}}
---
```

## Steps

1. Detect input type.
2. If URL → WebFetch + summarize to ~200 words.
3. Run routing rules → pick folder.
4. Generate filename (run hygiene rules).
5. Check for collision → resolve.
6. Write file with frontmatter + body.
7. Append entry to `{folders.meta}/captures.log` (JSONL: `{ts, folder, filename, source, confidence}`).
8. Echo to user: caveman one-liner. Pattern: `Captured → {{folder/filename}}. {{tag count}} tags.`

## Isolation guard (strict)

If content matches `isolation.patterns` AND user did not explicitly scope:
- If `overlap_with.context_patterns` also match → safe to route to `overlap_with.folder`
- Otherwise → REFUSE to write. Echo: `{{isolation.name}} content detected. Need explicit scope. Options: {{overlap_with.name}}-side (client/overlap) or {{isolation.name}}-direct (isolated, requires explicit "in {{isolation.folder}}" command).`

## Bulk capture mode

If user provides multiple items (numbered list, multiple URLs): run capture once per item, batch-log to `{folders.meta}/captures.log`. Output a table summary instead of per-line.

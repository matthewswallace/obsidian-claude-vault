---
name: connections
description: Surface non-obvious connections between vault notes. Given a topic, question, or existing note, finds related content across the vault and synthesizes what they say together. Use when user says "what have I thought about X", "find connections", "what relates to this", "synthesize my notes on Y", or "/connections".
---

# Connections

Retrieval-driven synthesis across the vault. The mental model: Claude is the agent doing the connecting — no external embedding service, no precomputed graph. Searches happen at query time using grep + targeted reads.

## When to invoke

User says variations of:
- "what have I been thinking about X?"
- "find connections to this"
- "what relates to [note]?"
- "synthesize my notes on Y"
- "what do my notes say about Z?"
- "build me a doc from my thinking on X"
- "/connections X"

## Two modes

**Mode A — Topic query.** User gives a topic/question. Find related notes, return synthesis.

**Mode B — Note expansion.** User points at an existing note. Find what else in the vault touches the same themes, surface the connections.

## Configuration

Read `.claude/vault.json` first:
- `isolation` — drop matches from the isolation folder unless explicitly scoped
- `folders.archive` — by default, search includes archive; can be told to skip
- `project_keywords` — boost matches in known projects

## Search strategy (in order)

1. **Frontmatter pre-filter** — if query mentions a known project (matches `project_keywords`), prioritize notes with that project tag.
2. **Body grep** — case-insensitive search for the topic terms across `*.md` files. Skip `.claude/`, `_meta/`, `_inbox/`. Skip `_archive/` unless user asked for "everything" or "archive".
3. **Title/filename match** — boost notes whose filename contains the topic terms.
4. **Wikilink graph** — if seed note is given, fetch notes that link to it AND notes it links to (1-hop neighborhood).

Cap the result set to **~20 most relevant** notes. Read each (Read tool, not bulk-scan). If a note is > 500 lines, read the first 100 + last 50.

## Synthesis pattern

Don't just list matches. Group + explain:

```markdown
# {{topic}} — connections across vault

## What you've explored

{{2-3 sentence synthesis grounded in the actual content read}}

## Core threads

### {{Theme 1}}
- `[[note A]]` — {{1-line: what this note adds}}
- `[[note B]]` — {{contrasts with A by ...}}

### {{Theme 2}}
...

## Tensions / open questions

{{If notes contradict each other or leave a question unresolved, name it}}

## Notes not yet connected

{{If any matched notes are too tangential to fit a theme, list them with brief context}}
```

Wikilinks `[[like this]]` use Obsidian's basename resolution — works as long as filenames are unique. If multiple notes have the same basename, use full path.

## Mode B specifics (note expansion)

When given a seed note:
1. Read the seed in full.
2. Extract its core concepts (3-5 key terms/themes).
3. For each, run mode-A search.
4. Synthesize as: "{{seed note title}} connects to {{N}} other threads in the vault."
5. Optional: at user's request, append a `## Related` section to the seed note with `[[wikilinks]]` to the surfaced notes.

## Doc-creation variant

If user says "build me a doc on X" or "create a synthesis":
1. Run connection search.
2. Write the synthesis as a new note. Default location: `My Stuff/synthesis/{{topic-slug}}.md` (or wherever the user specifies). If the folder doesn't exist, create it.
3. Filename hygiene: ≤60 chars, no UUIDs/emoji, Title Case.
4. Frontmatter:
   ```yaml
   ---
   created: {{YYYY-MM-DD}}
   tags: [synthesis, connections]
   source: connections-skill
   query: "{{original user query}}"
   sources: [{{list of [[wikilinks]] to source notes}}]
   ---
   ```
5. Body = the synthesis format above.

## Don't do these

- **Don't bulk-read the vault.** Search first, read targeted.
- **Don't invent connections.** Every theme/contrast you cite must be grounded in actual content from the read notes.
- **Don't include isolation-folder content** unless user explicitly scoped (`"include isolation"`, `"check {{isolation.folder}}"`, etc.).
- **Don't write synthesis to vault without asking** unless user said "create a doc" or "save this". Just printing the synthesis to chat is the default.

## Caveman output

If just answering in chat (not writing a doc), keep the synthesis tight — the structure above is the cap, not the floor. Cut sections that don't apply.

## Edge cases

- **Zero matches** → tell user honestly. Don't pad with tangential results. Suggest related queries.
- **Too many matches** (>100) → narrow with user. Ask which aspect of the topic they care about.
- **Conflicting notes** → don't smooth them out. Call out the contradiction explicitly. Conflicts are signal.

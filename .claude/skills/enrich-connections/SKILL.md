---
name: enrich-connections
description: Add semantic backlinks to a note's frontmatter using Smart Connections embeddings. Builds the neural-network layer of the vault by densifying the wikilink graph. Use when user says "enrich connections", "find related notes", "link this to similar notes", "/enrich".
---

# Enrich Connections

Densifies the vault graph by adding `related:` frontmatter entries based on Smart Connections similarity scores.

## When to invoke

- User says: "enrich connections", "find related to X", "link this to similar notes", "/enrich", "make graph denser"
- After triage: newly-routed notes should get connections
- Periodic (weekly): recent-notes pass

## How it works

1. Pick targets — single note, folder, or recently-modified
2. For each target, query `sc-query.py` for top-K semantic neighbors
3. Filter:
   - skip self
   - skip wikilinks already in body
   - skip below `--min-score` (default 0.6 — tight enough to avoid noise)
4. Add survivors to `related:` frontmatter (deduped)
5. Log per-file additions to `_meta/enrich.log`

## CLI

```bash
# Dry run on one note (default — shows what would be added)
python3 .claude/scripts/enrich-connections.py path "Banyan Labs/_index.md"

# Apply to a whole folder
python3 .claude/scripts/enrich-connections.py folder "My Stuff/personal" --apply

# Last 7 days of modified notes
python3 .claude/scripts/enrich-connections.py recent --days 7 --apply

# Tune
--limit 5            # max neighbors per note
--min-score 0.6      # cosine threshold
--apply              # write changes (default is dry run)
```

## Workflow

1. Pick scope (specific note, folder, recent).
2. Always run dry first.
3. Show the user the top adds per file.
4. Apply on confirm.
5. Note: after large changes, `sc-query.py stats` to confirm index health.

## Prereqs

- Smart Connections must have current embeddings — if stale, run `sc-cleanup.py --apply` and let Obsidian re-embed.
- Notes < 200 chars are not embedded (per `smart_env.json` `min_chars`).

## Why this matters

The user's goal is the vault as a "neural network" Claude can traverse to surface non-obvious connections. Direct wikilinks made manually are sparse. Smart Connections has 384-dim embeddings for every substantial note; this skill projects that latent graph into the explicit `related:` field that Dataview queries and Claude's own grep can use.

## Related

- `sc-query.py` — raw similarity CLI
- `sc-cleanup.py` — remove stale embeddings before enrichment
- `connections` skill — ad-hoc surfacing without writing changes

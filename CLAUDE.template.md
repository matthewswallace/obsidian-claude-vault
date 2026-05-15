# {{VAULT_NAME}} — Claude Operating Manual

This is an Obsidian vault with the [obsidian-claude-vault](https://github.com/{{GITHUB_USER}}/obsidian-claude-vault) automation scaffold installed. Optimize for **token economy** and **progressive disclosure**.

## Folder map

Vault-specific folder structure goes here. Edit to match your vault.

```
/                      vault root
├─ Daily/              daily notes (YYYY-MM-DD.md)
├─ Attachments/        images, pdfs, etc.
├─ _archive/           cold storage
├─ _meta/              auto-generated indices, logs
├─ _inbox/             temporary capture / unprocessed drops
├─ .claude/            scaffold + per-vault config (vault.json)
└─ .obsidian/          Obsidian config + plugins
```

Add your own top-level project folders here.

## Retrieval rules — READ BEFORE ACTING

1. **Never bulk-read folders.** Search before reading.
2. **Order of retrieval**:
   1. Check `_meta/vault-index.md` (table of contents) first
   2. For prose/concept search → grep + targeted file reads
   3. For metadata/tasks → Dataview query if Dataview is installed
   4. Only then `Read` the specific file(s)
3. **Daily notes** at `Daily/YYYY-MM-DD.md`. SessionStart hook injects today's note.
4. **Archive folders are cold storage.** Don't scan unless explicitly searching legacy content.
5. **Isolation rule:** `.claude/vault.json` defines an `isolation` block. The named folder is strictly isolated — never blend it with other folders or include it in cross-folder summaries unless explicitly scoped.
6. **Frontmatter is canonical.** When tagging/classifying, write to frontmatter, not body.

## Skills-first directive

Before responding to any non-trivial request:
1. Scan the active skills list for a match.
2. If match → invoke skill via `Skill` tool.
3. If no match but skill could exist → suggest creating one via `skill-creator`.
4. Only fall back to ad-hoc work if no skill fits.

Built-in vault skills (from this scaffold):
- `morning-brief` — populate today's daily note from calendar/email/tasks
- `capture` — route inbox content into the right folder
- `weekly-review` — Saturday roll-up

## Conventions

- **Frontmatter**: every note has `created`, `tags`, `project` (when applicable), `status` (when applicable)
- **Tags**: lowercase, hierarchical
- **Tasks**: use `- [ ]` checkbox syntax for Tasks plugin compatibility
- **Dates**: ISO 8601 (`YYYY-MM-DD`)

## Token-economy rules

- No comments in generated files unless they explain WHY
- Status updates in chat: one sentence per significant step, not per tool call
- Search before bulk-read

## Active integrations (MCP)

Edit this section to list your connected MCP servers and what they're used for.

## Configuration

Per-vault config lives at `.claude/vault.json` (gitignored — never committed). It defines:
- `isolation` — strict-folder + keyword rules
- `folders` — well-known folder names
- `project_keywords` — routing rules for captures/imports
- `triage_buckets` and `triage_clusters` — for `.claude/scripts/triage-themes.py`

Copy `.claude/vault.example.json` to `.claude/vault.json` and fill in your specifics.

## Long-running automation

Use the `schedule` skill for cron-style remote agents (run on Anthropic infra). Use local launchd + `.claude/scripts/obs.py` for jobs that need to write the vault directly.

## When in doubt

Search skills first. Search memory second. Search vault third. Ask the user fourth. Bulk-read never.

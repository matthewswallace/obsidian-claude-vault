# obsidian-claude-vault

Reusable automation scaffold for running Claude Code inside an Obsidian vault. Drop into any vault and get:

- **Session-start hook** — vault index + today's daily note auto-injected
- **Prompt-router hook** — pattern-matches your prompts to suggest the right skill (or warn about isolation rules)
- **Three built-in skills** — `morning-brief`, `capture`, `weekly-review`
- **Scripts** — Obsidian REST API wrapper, ChatGPT export importer, triage theme miner + applier, vault index builder
- **Per-vault config** at `.claude/vault.json` — folders, project keywords, strict-isolation rules. Gitignored so it never leaks.

The scaffold itself is generic. Your vault's specifics (employer name, project names, email, folder structure) live in `vault.json` which you fill in once.

## Install (5 minutes)

```bash
# 1. Clone the scaffold somewhere outside your vault
git clone https://github.com/YOU/obsidian-claude-vault.git ~/code/obsidian-claude-vault

# 2. Install into your vault
cd ~/code/obsidian-claude-vault
./install.sh "/path/to/your/Obsidian/Vault"

# 3. Edit the per-vault config
cd "/path/to/your/Obsidian/Vault"
$EDITOR .claude/vault.json     # set isolation, folders, project_keywords
$EDITOR CLAUDE.md              # customize folder map for your vault

# 4. (Optional) Install the Obsidian Local REST API plugin from Community Plugins
#    Then save the API key to ~/.config/obsidian-rest/key (mode 600)
mkdir -p ~/.config/obsidian-rest
echo -n "YOUR_API_KEY" > ~/.config/obsidian-rest/key
chmod 600 ~/.config/obsidian-rest/key

# 5. Open the vault in Claude Code
claude
```

## What goes where

```
<vault>/
├─ .claude/
│   ├─ scripts/             — Python/shell tools (from scaffold)
│   ├─ hooks/               — SessionStart + UserPromptSubmit (from scaffold)
│   ├─ skills/              — morning-brief, capture, weekly-review (from scaffold)
│   ├─ settings.json        — Claude Code permissions + hook wiring (from scaffold)
│   ├─ vault.example.json   — reference config (from scaffold)
│   └─ vault.json           — YOUR config (gitignored, never shared)
├─ CLAUDE.md                — your operating manual (from CLAUDE.template.md, customize)
└─ ...your vault content
```

## Configuration

`vault.json` minimum:

```json
{
  "vault_name": "My Vault",
  "user_email": "you@example.com",
  "isolation": {
    "name": "Acme Corp",
    "folder": "Acme",
    "patterns": ["acme"],
    "overlap_with": {
      "name": "ClientA",
      "folder": "ClientA",
      "context_patterns": ["clienta"]
    }
  },
  "folders": {
    "daily": "Daily",
    "archive": "_archive",
    "meta": "_meta",
    "inbox": "_inbox",
    "weekly_reviews": "Reviews"
  },
  "project_keywords": {
    "recipes": ["recipe", "ingredient"],
    "code": ["python", "javascript"]
  }
}
```

If you don't need strict isolation (no employer/client overlap), leave `isolation` blocks empty:

```json
"isolation": { "name": "", "folder": "", "patterns": [], "overlap_with": {} }
```

## Updating

Pull the latest scaffold, re-run `install.sh`. Your `vault.json` and `CLAUDE.md` are preserved.

```bash
cd ~/code/obsidian-claude-vault
git pull
./install.sh "/path/to/your/Obsidian/Vault"
```

## Scripts

| Script | What it does |
|--------|--------------|
| `obs.py` | Wrapper for Obsidian Local REST API. CLI + Python module. |
| `chatgpt-import.py` | Import ChatGPT export zip → markdown archive + index. Isolation pre-filter. |
| `triage-themes.py` | Read-only scan of triage buckets — flags filename hygiene issues, suggests moves. |
| `triage-apply.py` | Apply move/rename suggestions from triage-themes.py. Dry-run default, logged + reversible. |
| `build-vault-index.sh` | Build `_meta/vault-index.md` table of contents. Runs in SessionStart hook. |
| `vault_config.py` | Shared config loader (imported by other scripts). |

## Hooks

| Hook | Triggers on | What it does |
|------|-------------|--------------|
| `session-start.sh` | SessionStart | Emits today's daily note + folder counts + recent activity |
| `user-prompt-router.sh` | UserPromptSubmit | Pattern-matches prompt → suggests relevant skill + warns about isolation entity |

## Skills

| Skill | Trigger phrases |
|-------|-----------------|
| `morning-brief` | "morning brief", "start my day", "today's plan" |
| `capture` | "capture this", "save this", "file this" |
| `weekly-review` | "weekly review", "wrap up the week" |

All three respect the isolation config from `vault.json`.

## Requirements

- **Claude Code** — https://claude.com/claude-code
- **Python 3.8+** with `requests` (`pip install requests` — only for `obs.py`)
- **Obsidian** with [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) if you want background agents to write the vault
- **MCP connectors** (optional, for `morning-brief`/`weekly-review`): Google Calendar, Gmail, ClickUp — connect via claude.ai → Connectors

## Privacy

- `.claude/vault.json` is gitignored. Your employer/project/email never leave your machine.
- The REST API key lives in `~/.config/obsidian-rest/key` (outside the vault, mode 600). Never committed.
- No telemetry. Scripts are read-only-by-default; mutations log to `{folders.meta}/*.log` for reversibility.

## License

MIT — see [LICENSE](LICENSE).

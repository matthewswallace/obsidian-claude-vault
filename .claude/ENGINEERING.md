# Engineering practices — `.claude/` scaffold

This file is loaded into context whenever the user-prompt-router detects code, git, commit, test, or scaffold-modification intent. Treat it as binding when working on anything inside `.claude/` (scripts, hooks, commands, skills, settings).

## 1. Public-repo discipline (NON-NEGOTIABLE)

The `.claude/` scaffold is published to a public template repo (`github.com/matthewswallace/obsidian-claude-vault`). **Anything I write inside `.claude/` must ship cleanly to that repo** with no user-specific leakage.

**Forbidden in `.claude/` files:**
- Hardcoded absolute paths (`/Users/<name>/...`, cloud-sync mount prefixes)
- User identity (email, real name, real client/employer/project names)
- Private top-level folder names from the consuming vault — refer to them generically as "isolation entity" or read from `vault.json`
- Specific data values from the consuming vault's content
- API keys, tokens, or credentials of any kind

**Required pattern:**
- Derive paths via `VAULT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"` or equivalent
- Read user-specific config from `.claude/vault.json` (isolation, folder names, email)
- Use placeholder names in examples (`example-project/`, `<entity>`)
- If a script genuinely needs a user value, read it from `vault.json` and fail loudly if missing

**Self-check before any `.claude/` file write:** would this file be confusing or broken if a stranger cloned the template repo and dropped it into their vault? If yes, refactor.

## 2. Git workflow — trunk-based (simplified gitflow)

The vault content is NOT in git. The `.claude/` scaffold IS in git (via template repo). When working on scaffold:

**Branches:**
- `main` — known-good, deployable
- `feature/<slug>` — non-trivial work (new skill, new hook, schema change). Squash-merge to main.
- Skip `develop`, `release/*`, `hotfix/*` — solo author, no integration phase needed

**Commit hygiene:**
- One logical change per commit. Scripts + their hook registration + docs can be one commit if they belong together; new skill + unrelated bugfix should not.
- Conventional Commits format: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- Subject ≤ 50 chars. Body only when "why" isn't obvious from diff.
- Never commit `.env`, credentials, large binaries, generated artifacts (`_meta/*.log`, `_meta/*.jsonl`, `Attachments/`).

**Before commit checklist:**
- [ ] `git status` reviewed — no surprise files staged
- [ ] `git diff --staged` reviewed — no debug prints, no commented-out code
- [ ] No hardcoded user paths or identity (see §1)
- [ ] Pre-commit hooks pass without `--no-verify`
- [ ] Tests pass (or N/A explicitly noted)

**Before push to public repo:**
- [ ] `git log --oneline origin/main..HEAD` reviewed
- [ ] No force-push to main
- [ ] No bypassing hooks
- [ ] **Announce explicitly to user BEFORE push**: "About to push N commits to <branch>. <summary>. Proceed?" — wait for confirmation
- [ ] **Announce explicitly to user AFTER push**: "Pushed. Remote: <url>. HEAD: <sha>."

Same rule applies to: `git push --tags`, `gh pr create/merge/close`, `gh release *`, any remote-mutating op.

**Maintainer-only auto-sync Stop hook (`_maintainer/template-sync.sh`):**

The maintainer's working vault has a Stop hook at `.claude/_maintainer/template-sync.sh` that auto-pushes scaffold changes to the public template repo on turn end. **This hook lives in `_maintainer/` specifically so it does not ship to consumers** — it is excluded from the sync surface. Consumer vaults do not get it.

Synced surface (vault → template): `.claude/scripts/`, `.claude/skills/`, `.claude/hooks/`, `.claude/commands/`, root `.claude/*.md`.

Excluded from sync: `vault.json`, `settings.local.json`, `_maintainer/*`, scratch artifacts.

Discipline when working in a maintainer vault with this hook active:
- Any response that edits files in the synced surface must include a one-line pre-announcement: "Auto-sync: `<paths>` will push to template main at turn end."
- One consolidated notice per turn, listing all scaffold paths touched.
- For coherent multi-file features → use a feature branch in `~/code/obsidian-claude-vault` directly, NOT incremental auto-syncs.

## 3. Clean code

- **Names beat comments.** Rename rather than annotate. Comments are for *why*, never *what*.
- **No premature abstraction.** Three similar lines beats a too-clever helper. Extract on the third repetition, not the second.
- **Functions do one thing.** If you can't name it without "and", split it.
- **Error handling at boundaries.** Trust internal calls. Validate at the user-input / network edge.
- **Delete fearlessly.** Dead code, unused vars, stale docs — delete, don't comment out.
- **No backwards-compat shims** unless explicitly needed. Just change the call sites.

## 4. Clean architecture

For `.claude/` scaffold:
- **Hooks** = thin glue. Read stdin, route, exit. No business logic.
- **Scripts** = single-purpose. One verb in the filename. Reusable from CLI.
- **Skills** = workflow + prompt. No code; reference scripts for behavior.
- **Commands** = user-facing slash-commands. Minimal logic; delegate to skills/scripts.
- **Config** = `vault.json`. Single source of truth for paths, names, toggles. Never hardcode.

Direction of dependency: commands → skills → scripts → config. Never reverse.

## 5. TDD

Default for any non-trivial script in `.claude/scripts/`:

1. Write the test first (`tests/test_<name>.py` or `tests/test_<name>.sh`)
2. Watch it fail
3. Implement minimum to pass
4. Refactor with test as safety net

For shell scripts: `bats` or simple `#!/bin/bash` test files asserting exit codes + stdout. For Python: `pytest`.

When TDD is overkill (one-shot migration, exploratory spike): say so explicitly. Don't silently skip.

**Definition of "non-trivial":** > 20 lines, branches on state, touches filesystem destructively, or runs in a hook/automation.

## 6. Hooks discipline

Hooks fire automatically — broken hook = broken session. Therefore:
- Always `set -uo pipefail` (or equivalent)
- Always `exit 0` at the end unless intentionally blocking
- Never assume tools exist — gate `command -v jq >/dev/null || exit 0`
- Log to `/tmp/<hook-name>.log` on errors, never to stdout (stdout is injected into context)
- Keep < 200ms in the happy path; backgrounding (`& disown`) for anything slower

## 7. When in doubt

Ask. Confirm scope before destructive ops, public-facing writes, or anything irreversible. "I'll do X — sound right?" beats undoing X later.

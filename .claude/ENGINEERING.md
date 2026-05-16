# Engineering practices — `.claude/` scaffold

Binding rules for Claude Code agents working inside the `obsidian-claude-vault` scaffold. Surfaced into context whenever the `user-prompt-router.sh` hook detects code, git, commit, test, or scaffold-modification intent. Treat as authoritative when touching anything in `.claude/` (scripts, hooks, commands, skills, settings, docs).

## 1. Public-repo discipline (NON-NEGOTIABLE)

The `.claude/` scaffold ships as a **public template repo**. Anything written here must work cleanly when a stranger clones it into a fresh vault — no leaked identity, paths, or data from the vault that produced the change.

**Forbidden in scaffold files:**
- Hardcoded absolute paths (`/Users/<name>/...`, cloud-sync mount prefixes, OS-specific roots)
- User identity (email, real name, real client/employer/project names)
- Private top-level folder names from any consuming vault — refer to them generically as "isolation entity" or read from `.claude/vault.json`
- Specific data values from a consuming vault's content
- API keys, tokens, credentials of any kind

**Required pattern:**
- Derive paths via `VAULT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"` or equivalent
- Read consumer-specific config from `.claude/vault.json` (isolation, folder names, email)
- Use placeholder names in examples (`example-project/`, `<entity>`)
- If a script genuinely needs a consumer value, read it from `vault.json` and fail loudly if missing

**Self-check before any scaffold write:** would this file be confusing or broken if a stranger cloned the template and ran `./install.sh` against their own vault? If yes, refactor.

## 2. Git workflow — trunk-based (simplified gitflow)

**Branches:**
- `main` — known-good, deployable. Consumers track this.
- `feature/<slug>` — non-trivial work (new skill, new hook, schema change). Squash-merge to main.
- Skip `develop`, `release/*`, `hotfix/*` — solo or small-team scaffold, no integration phase needed.

**Commit hygiene:**
- One logical change per commit. A new skill + its hook registration + its docs can be one commit; a new skill + an unrelated bugfix cannot.
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- Subject ≤ 50 chars. Body only when *why* isn't obvious from the diff.
- Never commit `.env`, credentials, generated artifacts.

**Before commit:**
- [ ] `git status` reviewed — no surprise files staged
- [ ] `git diff --staged` reviewed — no debug prints, no commented-out code
- [ ] No hardcoded paths or identity (see §1)
- [ ] Pre-commit hooks pass without `--no-verify`
- [ ] Tests pass (or N/A explicitly noted)

**Before push:**
- [ ] `git log --oneline origin/main..HEAD` reviewed
- [ ] No force-push to main
- [ ] No bypassing hooks
- [ ] **Announce explicitly to the user BEFORE push**: "About to push N commits to <branch>. <summary>. Proceed?" — wait for confirmation
- [ ] **Announce explicitly to the user AFTER push**: "Pushed. Remote: <url>. HEAD: <sha>."

Same rule for: `git push --tags`, `gh pr create/merge/close`, `gh release *`, any remote-mutating op.

**Auto-sync Stop hook (optional, consumer-enabled):**

Some consumers wire a Stop hook (e.g. `template-sync.sh`) that auto-pushes scaffold changes from a working vault back upstream to this template repo. When such a hook is active:

- Any response that edits `.claude/scripts|skills|hooks/` must include a one-line pre-announcement: "Auto-sync: `<paths>` will push to template main at turn end."
- Consolidate into one notice per turn.
- Files outside the synced dirs (e.g. `.claude/ENGINEERING.md`, `.claude/commands/`, root `.claude/*.json`) DO NOT auto-sync — those require a manual feature-branch workflow.
- Coherent multi-file features → use a feature branch, not incremental auto-syncs.

## 3. Clean code

- **Names beat comments.** Rename rather than annotate. Comments are for *why*, never *what*.
- **No premature abstraction.** Three similar lines beats a too-clever helper. Extract on the third repetition, not the second.
- **Functions do one thing.** If you can't name it without "and", split it.
- **Error handling at boundaries.** Trust internal calls. Validate at the user-input / network edge.
- **Delete fearlessly.** Dead code, unused vars, stale docs — delete, don't comment out.
- **No backwards-compat shims** unless explicitly needed. Just change the call sites.

## 4. Clean architecture

Scaffold layers:
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
3. Implement the minimum to pass
4. Refactor with the test as safety net

Shell scripts → `bats` or plain `#!/bin/bash` test files asserting exit codes + stdout. Python → `pytest`.

When TDD is overkill (one-shot migration, exploratory spike): say so explicitly. Don't silently skip.

**Non-trivial =** > 20 lines, branches on state, touches filesystem destructively, or runs in a hook/automation.

## 6. Hooks discipline

Hooks fire automatically — broken hook = broken session. Therefore:
- Always `set -uo pipefail` (or equivalent)
- Always `exit 0` at the end unless intentionally blocking
- Never assume tools exist — gate `command -v jq >/dev/null || exit 0`
- Log to `/tmp/<hook-name>.log` on errors, never to stdout (stdout is injected into context)
- Keep < 200ms in the happy path; background (`& disown`) anything slower

## 7. When in doubt

Ask. Confirm scope before destructive ops, public-facing writes, or anything irreversible. "I'll do X — sound right?" beats undoing X later.

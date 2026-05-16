#!/usr/bin/env bash
# Auto-sync .claude/scripts/ and .claude/skills/ to template repo on Stop.
# Triggered by Claude Code Stop hook. Silent on no-op.
#
# Strategy:
#   1. Copy vault scripts/skills to template if newer or absent in template
#   2. Skip files in EXCLUDE list (vault-specific only)
#   3. If diff -> git add, commit, push (auto-message)
#   4. Fail soft: warn to stderr, never block

set -euo pipefail

VAULT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE_ROOT="${OBSIDIAN_CLAUDE_TEMPLATE:-$HOME/code/obsidian-claude-vault}"

# Exclude vault-specific paths (relative to .claude/)
EXCLUDES=(
  "vault.json"
  "settings.local.json"
  "scripts/triage-decisions-*.jsonl"
)

# Bail if template missing
if [[ ! -d "$TEMPLATE_ROOT/.git" ]]; then
  exit 0
fi

excluded() {
  local rel="$1"
  for pat in "${EXCLUDES[@]}"; do
    [[ "$rel" == $pat ]] && return 0
  done
  return 1
}

CHANGED=()
sync_tree() {
  local subdir="$1"
  local src_dir="$VAULT_ROOT/.claude/$subdir"
  local dst_dir="$TEMPLATE_ROOT/.claude/$subdir"
  [[ -d "$src_dir" ]] || return 0
  mkdir -p "$dst_dir"
  while IFS= read -r -d '' src; do
    rel="${src#$src_dir/}"
    excluded "$subdir/$rel" && continue
    dst="$dst_dir/$rel"
    mkdir -p "$(dirname "$dst")"
    if [[ ! -f "$dst" ]] || ! cmp -s "$src" "$dst"; then
      cp "$src" "$dst"
      CHANGED+=("$subdir/$rel")
    fi
  done < <(find "$src_dir" -type f -print0)
}

sync_tree scripts
sync_tree skills
sync_tree hooks

if [[ ${#CHANGED[@]} -eq 0 ]]; then
  exit 0
fi

cd "$TEMPLATE_ROOT"
git add -A >/dev/null 2>&1 || exit 0

# Skip if nothing actually staged (e.g. only excluded files diffed)
if git diff --cached --quiet; then
  exit 0
fi

# Build commit message
list=$(printf "%s\n" "${CHANGED[@]}" | sort -u | head -20)
MSG="Sync from vault: ${#CHANGED[@]} file(s)"
{
  git commit -m "$(cat <<EOF
$MSG

Auto-synced from vault on $(date -u +"%Y-%m-%dT%H:%M:%SZ"):

$list

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" >/dev/null 2>&1 \
  && git push origin main >/dev/null 2>&1
} || {
  echo "template-sync: commit/push failed — manual review needed at $TEMPLATE_ROOT" >&2
  exit 0
}

echo "template-sync: pushed ${#CHANGED[@]} file(s) to template repo" >&2

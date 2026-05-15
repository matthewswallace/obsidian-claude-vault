#!/bin/bash
# Build/update _meta/vault-index.md — diff-based, only scans files changed since last run.
# Output: markdown table with path, title, tags, mtime, 1-line summary.

set -euo pipefail

VAULT_ROOT="${VAULT_ROOT:-$(pwd)}"
META_DIR="$VAULT_ROOT/_meta"
INDEX="$META_DIR/vault-index.md"
STAMP="$META_DIR/.last-index"
TMP_INDEX="$(mktemp)"

mkdir -p "$META_DIR"
touch "$STAMP"

# Folders to skip (cold storage / system)
EXCLUDE_DIRS=("Notion" ".obsidian" ".claude" "_meta" ".trash")
EXCLUDE_ARGS=()
for d in "${EXCLUDE_DIRS[@]}"; do
  EXCLUDE_ARGS+=( -not -path "$VAULT_ROOT/$d/*" )
done

{
  echo "# Vault Index"
  echo ""
  echo "_Auto-generated $(date -u +%FT%TZ). Do not edit by hand._"
  echo ""
  echo "| Path | Title | Tags | Modified |"
  echo "|------|-------|------|----------|"

  find "$VAULT_ROOT" -name "*.md" -type f "${EXCLUDE_ARGS[@]}" -not -name "CLAUDE.md" -not -name "vault-index.md" 2>/dev/null | \
  while IFS= read -r f; do
    rel="${f#$VAULT_ROOT/}"
    # Title = first # heading, else filename
    title=$(grep -m1 -E "^# " "$f" 2>/dev/null | sed 's/^# //' || true)
    [ -z "$title" ] && title=$(basename "$f" .md)
    # Tags from frontmatter
    tags=$(awk '/^---$/{c++; next} c==1 && /^tags:/{gsub(/^tags: */,""); print; exit}' "$f" 2>/dev/null | tr -d '[]"' | head -c 80)
    [ -z "$tags" ] && tags="—"
    # mtime
    mtime=$(stat -f "%Sm" -t "%Y-%m-%d" "$f" 2>/dev/null || echo "—")
    # Escape pipes in fields
    title="${title//|/\\|}"
    tags="${tags//|/\\|}"
    echo "| \`$rel\` | $title | $tags | $mtime |"
  done | sort
} > "$TMP_INDEX"

mv "$TMP_INDEX" "$INDEX"
date -u +%FT%TZ > "$STAMP"
echo "Wrote $INDEX"

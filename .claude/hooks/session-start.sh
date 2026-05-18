#!/bin/bash
# SessionStart hook — runs on every Claude Code session start in this vault.
# Emits context to stdout that gets injected into the session.

set -uo pipefail

VAULT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$VAULT_ROOT"

TODAY=$(date +%Y-%m-%d)
CONFIG="$VAULT_ROOT/.claude/vault.json"
INDEX="_meta/vault-index.md"

cfg() {
  python3 - "$CONFIG" "$1" "$2" <<'PY' 2>/dev/null
import json
import sys
from pathlib import Path

path, dotted, default = sys.argv[1:4]
try:
    data = json.loads(Path(path).read_text())
except Exception:
    print(default)
    raise SystemExit

value = data
for part in dotted.split("."):
    value = value.get(part, {}) if isinstance(value, dict) else {}
if value in ({}, None, ""):
    value = default
print(value)
PY
}

DAILY_DIR="$(cfg folders.daily Daily)"
ARCHIVE_DIR="$(cfg folders.archive _archive)"
META_DIR="$(cfg folders.meta _meta)"
INBOX_DIR="$(cfg folders.inbox _inbox)"
ATTACHMENTS_DIR="$(cfg folders.attachments Attachments)"
ISOLATION_DIR="$(cfg isolation.folder __none__)"
DAILY="$DAILY_DIR/$TODAY.md"

# Refresh vault index in background (don't block session start)
( bash "$VAULT_ROOT/.claude/scripts/build-vault-index.sh" >/dev/null 2>&1 & )

echo "# Vault session context — $(date +%FT%T%z)"
echo ""
echo "Vault root: \`$VAULT_ROOT\`"
echo ""

# Today's daily note
if [ -f "$DAILY" ]; then
  echo "## Today's daily note (\`$DAILY\`)"
  echo ""
  head -c 4000 "$DAILY"
  echo ""
  echo ""
else
  echo "## Today's daily note"
  echo ""
  echo "_No daily note yet for $TODAY. Create with: \`$DAILY\`_"
  echo ""
fi

# Active projects — top-level folders not in exclude list
echo "## Top-level project folders"
echo ""
for d in */; do
  name="${d%/}"
  [ "$name" = ".obsidian" ] && continue
  [ "$name" = ".claude" ] && continue
  [ "$name" = ".smart-env" ] && continue
  [ "$name" = ".trash" ] && continue
  [ "$name" = "$META_DIR" ] && continue
  [ "$name" = "$ARCHIVE_DIR" ] && continue
  [ "$name" = "$DAILY_DIR" ] && continue
  [ "$name" = "$INBOX_DIR" ] && continue
  [ "$name" = "$ATTACHMENTS_DIR" ] && continue
  [ "$name" = "$ISOLATION_DIR" ] && continue
  count=$(find "$d" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "- \`$d\` ($count notes)"
done
echo ""

# Recent activity (last 7 days, top 10)
echo "## Recently modified (last 7 days, top 10)"
echo ""
find . -name "*.md" -type f -mtime -7 \
  -not -path "./.obsidian/*" -not -path "./.claude/*" \
  -not -path "./.smart-env/*" -not -path "./$META_DIR/*" \
  -not -path "./$ARCHIVE_DIR/*" -not -path "./$ATTACHMENTS_DIR/*" \
  -not -path "./$ISOLATION_DIR/*" \
  2>/dev/null | \
  xargs -I{} stat -f "%m %N" "{}" 2>/dev/null | \
  sort -rn | head -10 | \
  awk '{$1=""; print "- `" substr($0,2) "`"}'
echo ""

# Index pointer
if [ -f "$INDEX" ]; then
  size=$(wc -l < "$INDEX" | tr -d ' ')
  echo "## Vault index"
  echo ""
  echo "Full index: \`$INDEX\` ($size lines). Read it for table-of-contents view before searching."
  echo ""
fi

echo "---"
echo "_Caveman mode active. Skills-first. Search before reading. See \`CLAUDE.md\` for retrieval rules._"

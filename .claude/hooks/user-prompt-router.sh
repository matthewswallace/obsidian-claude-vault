#!/bin/bash
# UserPromptSubmit hook — pattern-match user prompts to suggest the right vault skill.
# Reads vault config from .claude/vault.json for isolation patterns.
# Reads hook JSON from stdin, emits hints to stdout (injected into next turn).

set -uo pipefail

INPUT=$(cat)
VAULT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONFIG="$VAULT_ROOT/.claude/vault.json"

PROMPT=$(echo "$INPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('prompt','').lower())" 2>/dev/null)

if [ -z "$PROMPT" ]; then
  exit 0
fi

# Pull isolation config from vault.json (defaults to empty if missing)
ISOLATION_NAME=""
ISOLATION_PATTERNS=""
OVERLAP_PATTERNS=""
if [ -f "$CONFIG" ]; then
  ISOLATION_NAME=$(python3 -c "import json; c=json.load(open('$CONFIG')); print((c.get('isolation') or {}).get('name',''))" 2>/dev/null)
  ISOLATION_PATTERNS=$(python3 -c "import json; c=json.load(open('$CONFIG')); ps=(c.get('isolation') or {}).get('patterns',[]); print('|'.join(ps))" 2>/dev/null)
  OVERLAP_PATTERNS=$(python3 -c "import json; c=json.load(open('$CONFIG')); ow=(c.get('isolation') or {}).get('overlap_with',{}); ps=ow.get('context_patterns',[]); print('|'.join(ps))" 2>/dev/null)
fi

SUGGESTIONS=()

# Morning brief
if echo "$PROMPT" | grep -qE "morning brief|start my day|today's plan|today schedule|what.s today|what.s on today"; then
  SUGGESTIONS+=("morning-brief — populate today's daily note from calendar/email/tasks")
fi

# Capture
if echo "$PROMPT" | grep -qE "capture this|save this|file this|where (does|should) this go|file (it|that) for me|/capture"; then
  SUGGESTIONS+=("capture — route inbox content into the right vault folder")
fi

# Weekly review
if echo "$PROMPT" | grep -qE "weekly review|week in review|wrap up the week|saturday review|how was my week"; then
  SUGGESTIONS+=("weekly-review — roll-up of the week's work")
fi

# Theme mining / connections
if echo "$PROMPT" | grep -qE "themes|patterns across|connections between|second brain mining|surface ideas|what.s in my archive"; then
  SUGGESTIONS+=("theme mining — read-only sweep of triage buckets, suggest connections")
fi

# Isolation guard (configurable)
if [ -n "$ISOLATION_PATTERNS" ] && echo "$PROMPT" | grep -qiE "$ISOLATION_PATTERNS"; then
  if [ -n "$OVERLAP_PATTERNS" ] && echo "$PROMPT" | grep -qiE "$OVERLAP_PATTERNS"; then
    SUGGESTIONS+=("⚠ $ISOLATION_NAME mentioned WITH client/overlap context — confirm scope before writing")
  else
    SUGGESTIONS+=("⚠ $ISOLATION_NAME mentioned — isolated. Confirm scope before writing.")
  fi
fi

# Filename hygiene reminder
if echo "$PROMPT" | grep -qE "move|rename|reorganiz|new folder|create.*folder|file rename"; then
  SUGGESTIONS+=("filename hygiene: strip UUIDs/hashes/emoji, drop redundant prefixes, ≤60 chars.")
fi

if [ ${#SUGGESTIONS[@]} -gt 0 ]; then
  echo "<vault-router>"
  echo "Skill/guard suggestions for this prompt:"
  for s in "${SUGGESTIONS[@]}"; do
    echo "- $s"
  done
  echo "</vault-router>"
fi

exit 0

#!/usr/bin/env bash
# SessionEnd hook — fires when Claude Code CLI exits.
# If /ob-exit set the sentinel, restart Obsidian.

SENTINEL=/tmp/ob-restart-pending

if [ -f "$SENTINEL" ]; then
  rm -f "$SENTINEL"
  # Detach so hook returns immediately; Obsidian restart runs independently.
  VAULT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  nohup bash "$VAULT_ROOT/scripts/restart-obsidian.sh" > /tmp/ob-restart.log 2>&1 &
  disown
fi

exit 0

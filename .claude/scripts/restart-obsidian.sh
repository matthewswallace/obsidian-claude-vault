#!/usr/bin/env bash
# Quit Obsidian cleanly, wait, relaunch.
# Used by /ob-exit slash command via SessionEnd hook.

set -e

LOG=/tmp/ob-restart.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] restart-obsidian.sh fired" >> "$LOG"

if pgrep -x Obsidian >/dev/null 2>&1; then
  echo "[$(date '+%H:%M:%S')] Obsidian running — sending quit" >> "$LOG"
  osascript -e 'tell application "Obsidian" to quit' 2>/dev/null || true

  # Wait up to 10s for clean exit
  for i in {1..10}; do
    if ! pgrep -x Obsidian >/dev/null 2>&1; then
      echo "[$(date '+%H:%M:%S')] Obsidian quit after ${i}s" >> "$LOG"
      break
    fi
    sleep 1
  done

  # Force-kill if still running
  if pgrep -x Obsidian >/dev/null 2>&1; then
    echo "[$(date '+%H:%M:%S')] Obsidian still alive — SIGTERM" >> "$LOG"
    pkill -x Obsidian 2>/dev/null || true
    sleep 2
  fi
fi

echo "[$(date '+%H:%M:%S')] launching Obsidian" >> "$LOG"
open -a Obsidian
echo "[$(date '+%H:%M:%S')] done" >> "$LOG"

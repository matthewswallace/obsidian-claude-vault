---
description: Exit Claude session and restart Obsidian
---

User invoked `/ob-exit` — they want to exit Claude and restart Obsidian.

You cannot kill your own process. The pattern is:

1. Write sentinel file `/tmp/ob-restart-pending` (touch it).
2. Tell user in ONE short line: "Sentinel armed. Type /exit (or Ctrl+D) to fire restart."
3. Do NOT do anything else. Do not summarize. Do not offer follow-ups.

The SessionEnd hook (`.claude/hooks/session-end.sh`) detects the sentinel on exit and runs `.claude/scripts/restart-obsidian.sh`, which quits Obsidian (clean → force after 10s) and relaunches it.

Use the Bash tool to run:
```
touch /tmp/ob-restart-pending
```

Then output the one-line confirmation.

# Daily ChatGPT Learning Agent

Run daily at 05:30 CDT (before morning brief) to extract patterns, suggest connections, and learn from vault activity.

## Job

1. **Vault snapshot:** What changed in last 24h?
   - New files created (by tag + path)
   - File modifications (titles, tags, frontmatter)
   - Deleted files (if tracked)
   
2. **ChatGPT corpus analysis:**
   - For today's date: which conversations exist in that month?
   - Reindex top projects/themes if new files suggest pattern shift
   - Detect emerging keywords from new vault files vs ChatGPT patterns
   
3. **Pattern extraction:**
   - Voice patterns: analyze recent Matthew writing (vault new files) vs ChatGPT data for linguistic fingerprint
   - Project clusters: group ChatGPT conversations by implicit projects (not just detected keywords)
   - Time patterns: which time of day does Matthew work on what?
   - Cross-domain: where do topics from Banyan, personal, and Vant4ge intersect?
   
4. **Generate suggestions:**
   - Top 3 connection ideas (file X in vault relates to ChatGPT conversation Y; why?)
   - Top 1 new project idea (based on patterns, what might Matthew want to start?)
   - Top 1 refinement suggestion (how should a current vault folder evolve?)
   
5. **Confidence scoring:**
   - Each suggestion gets a score 0.0–1.0
   - Only propose if score ≥0.7
   - Track: did Matthew act on this suggestion? (adjust confidence next cycle)
   
6. **Output:**
   - Append to `_meta/daily-insights.md` with timestamp
   - Update `_meta/connection-queue.md` with new suggestions
   - Auto-tag any high-confidence suggestions in vault
   
7. **Learning:**
   - Log decision rationales to `_meta/chatgpt-analysis/daily-log.jsonl`
   - Monthly agent aggregates into rollup insights

## Constraints

- **Isolation:** Never blend Vant4ge/ with other folders unless Matthew explicitly asks
- **Token budget:** Keep analysis compact; use jcodemunch for vault queries
- **Reversibility:** All decisions logged; can audit why suggestion was made
- **Human override:** If Matthew rejects a suggestion 3x in a row, suppress that suggestion type (log reason)

## Implementation

Run via `schedule` skill:
- Cron: `30 05 * * 1-5` (05:30 CDT, Mon–Fri)
- Trigger: remote agent with this prompt + recent context
- Output: append/update files in `_meta/`
- Notify: if confidence ≥0.9 on high-impact suggestion, notify Matthew

## Success Metrics (Monthly Review)

- Suggestions made: N (target: 30/month = 6/week)
- Suggestions acted on: Y (target: ≥30%)
- New projects created from suggestions: Z
- Confidence calibration: (suggestions ≥0.8) / (actual outcomes) (target: >80% accuracy)

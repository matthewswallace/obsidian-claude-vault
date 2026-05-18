# Monthly ChatGPT Rollup Agent

Run on 1st of month at 06:00 CDT to synthesize 30 days of daily insights, adjust tuning, and forecast.

## Job

1. **Aggregate daily insights:**
   - Read `_meta/chatgpt-analysis/daily-log.jsonl` (last 30 days)
   - Count suggestions by type
   - Calculate acceptance rate
   - Identify suggestions that generated vault changes
   
2. **Theme evolution:**
   - Which project themes emerged or faded?
   - Did Matthew start any new projects?
   - Did topic clusters shift (e.g., "Banyan + Vant4ge" → separate silos)?
   
3. **Voice fingerprint refinement:**
   - Did Matthew's writing style change? (seasonal? cyclical?)
   - Which ChatGPT patterns best predict new vault activity?
   - Update linguistic "taste profile" for daily agent
   
4. **Folder structure audit:**
   - Recommend new folders based on patterns
   - Flag orphaned/underpopulated folders
   - Suggest tag additions or consolidations
   
5. **Agent tuning:**
   - Which suggestion types had highest acceptance? Boost confidence threshold.
   - Which had lowest acceptance? Suppress or redesign.
   - Update `.claude/daily-chatgpt-agent.md` with refined heuristics
   
6. **Forecast:**
   - Top 3 projects Matthew is likely to tackle in next month
   - Top 2 topics worth deep-diving into next
   - 1 predicted major pivot or shift
   
7. **Output:**
   - Write `_meta/chatgpt-analysis/YYYY-MM-rollup.md` (this month's report)
   - Update `_meta/chatgpt-project.md` success metrics
   - Create `_meta/chatgpt-analysis/forecast-YYYY-MM.md` (next month predictions)
   - Auto-create vault folders/MOCs if confidence ≥0.85

## Structure: Monthly Report

```
# May 2026 ChatGPT Rollup

## Summary
- Suggestions made: 26
- Acceptance rate: 62%
- New projects started: 2
- Major themes: Banyan, music production, personal/faith

## Theme Evolution
- Banyan: ↑ (new client work)
- Vant4ge: → (stable, no new patterns)
- Personal: ↑ (health focus increasing)

## Voice Fingerprint
- Matthew increasingly asks "what if" questions (vs problem-solving)
- Code + design discussions rising
- Music production returning after 3-month gap

## Suggested Actions
- [ ] Create Music Production MOC (auto-created: folder ready)
- [ ] Merge two small Banyan sub-projects (related conversations detected)
- [ ] Archive 2026-01-Q1 personal/finance notes (clear pattern: consolidated)

## Forecast (June 2026)
1. Likely: Mobile app design for Banyan client
2. Likely: Church/faith-based technical project
3. Possible: Solo music recording project

## Agent Tuning
- Boost: connection suggestions (62% acceptance)
- Reduce: project creation suggestions (33% acceptance)
- Add: seasonal pattern detection (noticed Q2 shift)
```

## Constraints

- **Conservative:** Only recommend major changes if confidence ≥0.90
- **Reversibility:** Archive old rollups; keep history for trend analysis
- **Isolation:** Maintain Vant4ge separation; flag only if Matthew explicitly connects

## Implementation

Run via `schedule` skill:
- Cron: `0 06 1 * *` (06:00 CDT on 1st of month)
- Trigger: remote agent with this prompt + 30-day log context
- Notify: Matthew if forecast includes high-confidence surprises

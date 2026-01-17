# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-15)

**Core value:** Accurate and reliable data scraping from both sources without errors or missing data
**Current focus:** v2.0 Analytics complete — All milestones shipped

## Current Position

Phase: 7 of 7 (Advanced Value)
Plan: 2 of 2 complete
Status: Milestone complete
Last activity: 2026-01-17 — Completed 07-02-PLAN.md

Progress: ██████████ 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 19
- Average duration: ~2 hours per plan
- Total execution time: ~38 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 4 | ~8h | ~2h |
| 2. Stats Scraper | 3 | ~6h | ~2h |
| 3. Odds Scraper | 3 | ~6h | ~2h |
| 4. Dashboard | 3 | ~6h | ~2h |
| 5. Race Results | 2 | ~4h | ~2h |
| 6. Pattern Analysis | 2 | ~4h | ~2h |
| 7. Advanced Value | 2 | ~4h | ~2h |

**Recent Trend:**
- Last 5 plans: All successful
- Trend: Stable

## Current System Stats

- **Dogs in DB**: 342 with full stats
- **Races tracked**: 45 upcoming
- **Odds records**: 3,628
- **Tracks covered**: Central Park, Dunstall Park, Hove, Limerick, Towcester, Valley

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Key decisions made during development:

- Web dashboard interface chosen for accessibility
- Separate refresh cycles (daily stats, real-time odds) to optimize scraping
- Flask chosen over FastAPI/Django for simplicity
- Top 5 bookmakers only (Bet365, William Hill, Paddy Power, Sky Bet, Betfred)
- Value threshold: 1.2+ (20% edge minimum)
- Auto-refresh every 60 seconds
- PostgreSQL for data persistence
- Playwright with stealth mode for anti-bot bypass

### Technical Notes

- Irish tracks (Valley, Limerick) don't display trap numbers on oddschecker
- Trap numbers extracted from `.trap-cell` HTML element
- Auto-cleanup now preserves completed races (status='complete'), only removes scheduled
- Dog name fuzzy matching handles variations between sources
- Results scraper extracts from oddschecker results page with SP and finish times
- Value bets automatically recorded to bet_history when identified

### Deferred Issues

None.

### Pending Todos

None.

### Blockers/Concerns

- Grade and distance not available on oddschecker pages (shows N/A)
- Some Irish track races lack trap number display

### Roadmap Evolution

- v1.0 MVP shipped: 2026-01-15, Phases 1-4
- v2.0 Analytics created: 2026-01-15, Phases 5-7 (Historical Tracking, Pattern Analysis, Advanced Value)

## Session Continuity

Last session: 2026-01-17
Stopped at: v2.0 Analytics milestone complete
Resume file: None

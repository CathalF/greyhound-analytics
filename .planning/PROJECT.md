# Greyhound Racing Value Finder

## What This Is

A web-based application that scrapes greyhound racing data from greyhoundstats.co.uk and live odds from oddschecker, comparing them to identify value betting opportunities. Users can manually research races with both datasets side-by-side, receive betting recommendations based on statistical analysis, and track patterns over time to refine their strategy.

## Core Value

Accurate and reliable data scraping from both sources without errors or missing data. Everything else builds on this foundation.

## Requirements

### Validated

- [x] Daily scraping of greyhound statistics from greyhoundstats.co.uk
- [x] Real-time odds scraping from oddschecker
- [x] Comparison logic that identifies dogs with strong stats relative to their odds
- [x] Web dashboard displaying current races with combined stats and odds
- [x] Manual research interface to browse and analyze races
- [x] Value bet identification highlighting potential opportunities

### Active

- [ ] Historical race tracking to identify patterns and trends
- [ ] Betting recommendations based on stat/odds analysis (beyond basic value score)

### Out of Scope

- Automated betting (no actual bet placement) — v1 is analysis only, user places bets manually
- Mobile app (desktop/web only) — focus on functionality first, mobile later
- Multiple sports (greyhounds only) — avoid scope creep into horses or other racing
- Historical archives beyond pattern tracking — not building a comprehensive race database

## Context

This application targets the intersection of two data sources that bettors typically check separately. Greyhoundstats.co.uk provides historical performance data (win rates, track preferences, recent form), while oddschecker shows current market odds. The value proposition is identifying discrepancies where statistical performance suggests better odds than the market offers.

Key implementation considerations:
- Both sites will have anti-scraping measures (rate limiting, CAPTCHAs, IP blocks)
- Odds change frequently as race time approaches
- Stats data is relatively stable but needs daily refresh for new races
- Users need to act quickly on value bets before odds shift

## Constraints

- **Budget**: Free/cheap hosting and services only — no paid APIs or premium infrastructure
- **Rate Limiting**: Must respect both sites' rate limits to avoid IP blocks — scraping must be polite and sustainable
- **Real-time odds**: Oddschecker data needs to refresh frequently (every few minutes) close to race time
- **Stats refresh**: Greyhoundstats data can be batch updated daily

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Web dashboard interface | Accessible from any device, easier to iterate | Implemented with Flask |
| Separate refresh cycles (daily stats, real-time odds) | Optimizes scraping load and respects rate limits | Working well |
| Flask over FastAPI/Django | Simpler for MVP, less boilerplate | Good choice |
| PostgreSQL for storage | Reliable, free tier available, JSONB for stats | Working well |
| Playwright with stealth mode | Bypasses anti-bot detection | Effective |
| Top 5 bookmakers only | Reduces noise, focuses on major UK bookies | Clean display |
| Value threshold 1.2+ | 20% edge minimum balances opportunities vs noise | Good balance |
| Auto-refresh 60 seconds | Keeps odds current without hammering server | Appropriate |

---
*Last updated: 2026-01-15 after MVP completion*

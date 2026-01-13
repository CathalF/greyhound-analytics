# Greyhound Racing Value Finder

## What This Is

A web-based application that scrapes greyhound racing data from greyhoundstats.co.uk and live odds from oddschecker, comparing them to identify value betting opportunities. Users can manually research races with both datasets side-by-side, receive betting recommendations based on statistical analysis, and track patterns over time to refine their strategy.

## Core Value

Accurate and reliable data scraping from both sources without errors or missing data. Everything else builds on this foundation.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Daily scraping of greyhound statistics from greyhoundstats.co.uk
- [ ] Real-time odds scraping from oddschecker
- [ ] Comparison logic that identifies dogs with strong stats relative to their odds
- [ ] Web dashboard displaying current races with combined stats and odds
- [ ] Manual research interface to browse and analyze races
- [ ] Value bet identification highlighting potential opportunities
- [ ] Historical race tracking to identify patterns and trends
- [ ] Betting recommendations based on stat/odds analysis

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
| Web dashboard interface | Accessible from any device, easier to iterate | — Pending |
| Separate refresh cycles (daily stats, real-time odds) | Optimizes scraping load and respects rate limits | — Pending |
| Historical tracking included in v1 | Pattern analysis adds significant value to recommendations | — Pending |

---
*Last updated: 2026-01-13 after initialization*

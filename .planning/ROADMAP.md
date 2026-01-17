# Roadmap: Greyhound Racing Value Finder

## Overview

Build a web-based greyhound racing value finder from ground up: establish scraping infrastructure and data models, implement daily stats scraping from greyhoundstats.co.uk, add real-time odds scraping from oddschecker, then deliver a web dashboard that compares both datasets to identify value betting opportunities.

## Domain Expertise

Greyhound racing scraping: Playwright with stealth mode for anti-bot bypass, token bucket rate limiting, dog name fuzzy matching between sources.

## Milestones

- ✅ **v1.0 MVP** - Phases 1-4 (shipped 2026-01-15)
- ✅ **v2.0 Analytics** - Phases 5-7 (shipped 2026-01-17)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>✅ v1.0 MVP (Phases 1-4) - SHIPPED 2026-01-15</summary>

### Phase 1: Foundation
**Goal**: Establish project structure, scraping infrastructure, and core data models for races, dogs, and odds
**Depends on**: Nothing (first phase)
**Status**: Complete

**Implemented**:
- PostgreSQL database with dogs, races, odds tables
- Base scraper with Playwright + stealth mode (`src/scrapers/base_scraper.py`)
- Token bucket rate limiter (`src/utils/rate_limiter.py`)
- Database abstraction layer (`src/storage/db.py`)

Plans:
- [x] 01-01: Project structure and database schema
- [x] 01-02: Base scraper infrastructure
- [x] 01-03: Rate limiting implementation
- [x] 01-04: Stealth mode configuration

### Phase 2: Stats Scraper
**Goal**: Implement reliable daily scraping of greyhound statistics from greyhoundstats.co.uk
**Depends on**: Phase 1
**Status**: Complete

**Implemented**:
- Dog stats scraper (`src/scrapers/greyhound_stats_scraper.py`)
- Stats extraction: runs, wins, win_rate, track_stats, distance_stats, recent_form
- Batch scraping with resume capability
- 342 dogs with stats in database

Plans:
- [x] 02-01: Greyhoundstats HTML analysis
- [x] 02-02: Dog stats scraper implementation
- [x] 02-03: Batch scraping with logging

### Phase 3: Odds Scraper
**Goal**: Implement real-time odds scraping from oddschecker with frequent refresh capability
**Depends on**: Phase 2
**Status**: Complete

**Implemented**:
- Oddschecker scraper (`src/scrapers/oddschecker_scraper.py`)
- Race discovery from listing page
- Trap number extraction from HTML (handles vacant traps)
- Odds extraction: 20+ bookmakers with decimal/fractional formats
- Dog name matching between oddschecker and greyhoundstats
- Auto-cleanup of old races after they pass

Plans:
- [x] 03-01: Oddschecker structure analysis
- [x] 03-02: Race and odds scraper implementation
- [x] 03-03: Dog matching and linking

### Phase 4: Dashboard & Analysis
**Goal**: Build web dashboard displaying races with combined stats/odds, value identification, and betting recommendations
**Depends on**: Phase 3
**Status**: Complete

**Implemented**:
- Flask web app (`src/app.py`)
- Dashboard home page with upcoming races
- Race detail page with dogs, stats, and odds comparison
- Value finder algorithm (`src/services/value_finder.py`)
- Top 5 bookmaker filtering (Bet365, William Hill, Paddy Power, Sky Bet, Betfred)
- Auto-refresh every 60 seconds
- Value threshold: 1.2+ (20% edge)

Plans:
- [x] 04-01: Flask setup and templates
- [x] 04-02: Dashboard and race detail pages
- [x] 04-03: Value finder integration

</details>

<details>
<summary>✅ v2.0 Analytics (Phases 5-7) - SHIPPED 2026-01-17</summary>

**Milestone Goal:** Add historical tracking of race outcomes and enhance the value algorithm with track/distance/form weighting for better betting predictions.

#### Phase 5: Race Results
**Goal**: Store race outcomes and track betting history to enable pattern analysis
**Depends on**: v1.0 complete
**Research**: Unlikely (internal patterns - extending existing database)
**Status**: Complete

**Implemented**:
- race_results and bet_history database tables
- Result and BetRecord models (`src/models/result.py`)
- Storage layer (`src/storage/race_results.py`)
- Results scraper from oddschecker (`src/scrapers/results_scraper.py`)
- Value finder integration with automatic bet recording
- Results collector script (`src/results_collector.py`)
- Cleanup modified to preserve completed races

Plans:
- [x] 05-01: Database schema and storage layer (race_results, bet_history tables)
- [x] 05-02: Results scraper and value finder integration

#### Phase 6: Pattern Analysis
**Goal**: Analyze historical race data to identify winning patterns and trends
**Depends on**: Phase 5
**Research**: Unlikely (internal patterns - data analysis on existing schema)
**Status**: Complete

**Implemented**:
- Pattern analyzer service with 6 analysis functions (`src/services/pattern_analyzer.py`)
- Track performance, value score buckets, form correlation, trap bias, time of day analysis
- Betting summary with win rate, ROI, and streak tracking
- CLI script for pattern analysis (`src/analyze_patterns.py`)
- Dashboard /patterns page with comprehensive visualizations
- Navigation integration in global navbar

Plans:
- [x] 06-01: Pattern analyzer service (track, value score, form, trap analysis)
- [x] 06-02: Dashboard integration (/patterns page)

#### Phase 7: Advanced Value
**Goal**: Enhance value algorithm with track-specific performance, distance weighting, recent form trends, and trap bias
**Depends on**: Phase 6
**Research**: Unlikely (internal patterns - algorithm refinement)
**Status**: Complete

**Implemented**:
- Advanced value calculator with 5-factor weighting (`src/services/advanced_value.py`)
- Factors: base value (40%), track (20%), form (20%), trap bias (10%), time of day (10%)
- Confidence levels (high/medium/low) based on data availability
- 30-minute caching for pattern data
- Value finder integration with advanced scoring mode
- API endpoints for value analysis (`src/routes/api.py`)
- Race detail page with factor breakdown visualization
- Dashboard top value bets summary card with confidence indicators

Plans:
- [x] 07-01: Advanced value calculator with 5-factor weighting (track, form, trap, time)
- [x] 07-02: Dashboard integration with factor visualization

</details>

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 4/4 | Complete | 2026-01-13 |
| 2. Stats Scraper | v1.0 | 3/3 | Complete | 2026-01-14 |
| 3. Odds Scraper | v1.0 | 3/3 | Complete | 2026-01-14 |
| 4. Dashboard & Analysis | v1.0 | 3/3 | Complete | 2026-01-15 |
| 5. Race Results | v2.0 | 2/2 | Complete | 2026-01-15 |
| 6. Pattern Analysis | v2.0 | 2/2 | Complete | 2026-01-17 |
| 7. Advanced Value | v2.0 | 2/2 | Complete | 2026-01-17 |

## Current Stats

- **Dogs**: 342 with full stats
- **Races**: 45 upcoming
- **Odds**: 3,628 records
- **Tracks**: Central Park, Dunstall Park, Hove, Limerick, Towcester, Valley

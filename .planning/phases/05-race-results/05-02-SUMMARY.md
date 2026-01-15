---
plan_id: 05-02
phase: 05-race-results
status: complete
completed_at: 2026-01-15T17:10:00Z
tasks_completed: 3/3
---

# Plan 05-02 Summary: Results Scraper and Value Finder Integration

## Objective
Scrape race results and integrate with value finder to track bet outcomes.

## Tasks Completed

### Task 1: Create results scraper
- Created `src/scrapers/results_scraper.py` extending BaseScraper
- Implemented `ResultsScraper` class for oddschecker results page
- Added `scrape_results_page()` to get all today's race results
- Added `scrape_race_result()` to get specific race by track and time
- Added `match_result_to_race()` to link scraped dogs to database using fuzzy matching
- Extracts finishing positions (1-6), SP (starting price), and finishing times
- Supports multiple HTML structures with fallback selectors

### Task 2: Integrate value finder with bet recording
- Modified `find_value_bets_for_race()` to accept `record_bets=True` parameter
- Added `_record_value_bets()` helper to store bets in bet_history table
- Added `get_tracked_value_bets()` to retrieve bets with outcome status (pending/won/lost)
- Added `update_value_bet_outcomes()` to update pending bets after races complete
- Added `find_and_record_all_value_bets()` convenience function for batch recording
- Only records new bets (skips if race+dog combination already exists)

### Task 3: Create results collector script
- Created `src/results_collector.py` as CLI script for scheduled results collection
- Implemented `collect_results()` to scrape and store race results
- Implemented `print_summary()` to show collection stats and betting performance
- CLI flags:
  - `--stats`: Show betting statistics only (no scraping)
  - `--force`: Re-scrape even if results already exist
  - `--verbose`: Enable debug logging
- Added proper logging with timestamps
- Looks back 6 hours for missed results
- Intended to run every 30 minutes via cron/scheduler

## Files Modified
- `src/scrapers/results_scraper.py` - New file with ResultsScraper class
- `src/services/value_finder.py` - Added bet recording integration and new functions
- `src/results_collector.py` - New file with collector script and CLI

## Verification
- [x] Results scraper extracts positions from oddschecker
- [x] Value finder records bets to bet_history table
- [x] Results collector updates outcomes
- [x] `python src/results_collector.py --stats` shows betting statistics

## Commits
1. `d5308dd` - feat(05-02): Create results scraper for race outcomes
2. `e30c3ac` - feat(05-02): Integrate value finder with bet recording
3. `2a6bdcc` - feat(05-02): Create results collector script

## Deviations
None - all tasks completed as specified.

## Notes
- Results scraper uses flexible selectors to handle oddschecker's varying HTML structures
- Value finder only records bets when explicitly requested (record_bets=True)
- Collector script handles graceful degradation when results not found
- Phase 5 (Race Results) is now complete with both plans finished

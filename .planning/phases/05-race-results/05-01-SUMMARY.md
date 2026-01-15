---
plan_id: 05-01
phase: 05-race-results
status: complete
completed_at: 2026-01-15T17:05:00Z
tasks_completed: 3/3
---

# Plan 05-01 Summary: Database Schema and Storage Layer

## Objective
Add database schema and storage layer for race results and betting history to enable historical tracking.

## Tasks Completed

### Task 1: Add race_results and bet_history tables to schema
- Added `race_results` table with columns: result_id, race_id, dog_id, position, finishing_time, starting_price, created_at
- Added `bet_history` table with columns: bet_id, race_id, dog_id, suggested_at, value_score, best_odds, best_bookmaker, outcome, actual_position, profit_loss, created_at
- Created indexes for efficient lookups (race_id, outcome)
- Tables created with CREATE TABLE IF NOT EXISTS for idempotency

### Task 2: Create Result model and storage functions
- Created `src/models/result.py` with Result and BetRecord dataclasses
- Both models include to_dict() and from_dict() methods following existing patterns
- Created `src/storage/race_results.py` with functions:
  - insert_race_results(): Insert multiple result records for a race
  - get_race_results(): Get all results for a race by position
  - record_value_bet(): Record a suggested value bet
  - update_bet_outcome(): Update bet records with actual positions and profit/loss after race
  - get_betting_history(): Get recent bet history with outcomes
  - get_betting_stats(): Return summary stats (total bets, wins, losses, win_rate, profit, ROI)

### Task 3: Modify cleanup to preserve completed races
- Modified `cleanup_old_races()` to only delete races where race_time < cutoff AND status = 'scheduled'
- Completed races (status='complete') are now preserved for historical analysis
- Added `mark_race_complete()` function to update race status after results recorded

## Files Modified
- `src/storage/schema.sql` - Added race_results and bet_history tables with indexes
- `src/models/result.py` - New file with Result and BetRecord dataclasses
- `src/storage/race_results.py` - New file with storage functions
- `src/storage/race_odds.py` - Modified cleanup_old_races(), added mark_race_complete()

## Verification
- [x] `python -m src.storage.migrations` runs without errors
- [x] race_results and bet_history tables exist in database
- [x] All storage functions importable and callable
- [x] cleanup_old_races() preserves completed races

## Commits
1. `e3c9188` - feat(05-01): Add race_results and bet_history tables to schema
2. `e1bb06e` - feat(05-01): Create Result model and storage functions
3. `4590c2f` - feat(05-01): Modify cleanup to preserve completed races

## Deviations
None - all tasks completed as specified.

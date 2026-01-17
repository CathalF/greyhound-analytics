# 07-01 Summary: Advanced Value Calculator

## Completed
- Task 1: Created advanced value calculator service with 5-factor weighted scoring algorithm
- Task 2: Integrated advanced scoring into value finder with use_advanced parameter
- Task 3: Added --advanced CLI flag to analyze_patterns.py with factor breakdown display

## Files Modified
- src/services/advanced_value.py (new)
- src/services/value_finder.py
- src/analyze_patterns.py

## Commits
- 301c603: feat(07-01): Create advanced value calculator service
- 838f627: feat(07-01): Integrate advanced scoring into value finder
- ab52952: feat(07-01): Add advanced value CLI command

## Verification
- [x] Imports OK - `from src.services.advanced_value import *` works
- [x] Advanced scoring works - produces different values than basic scoring (1.2000 vs 1.2400)
- [x] CLI --advanced flag works - shows in help and runs correctly

## Implementation Details

### Advanced Value Calculator (advanced_value.py)
- **5-factor weighting system:**
  - Base Value (40%): win_rate / implied_probability
  - Track Factor (20%): track-specific win rate ratio
  - Form Factor (20%): recent form analysis (strong/moderate/weak)
  - Trap Factor (10%): historical trap win rates from pattern_analyzer
  - Time Factor (10%): time-of-day ROI patterns from pattern_analyzer
- **Confidence levels:** high/medium/low based on data availability
- **30-minute caching** for trap_bias and time_analysis data
- **Helper functions:** Individual factor calculations, explanation generation

### Value Finder Integration (value_finder.py)
- Added `use_advanced` parameter (default: True)
- New thresholds: ADVANCED_VALUE_THRESHOLD (1.25), ADVANCED_STRONG_VALUE_THRESHOLD (1.5)
- Returns advanced_score, factor_breakdown, and confidence in value bets
- Sorts by advanced_score when use_advanced=True

### CLI (analyze_patterns.py)
- New `--advanced` flag for advanced value analysis
- New `--hours` flag to configure scan window (default: 4)
- Displays factor breakdown for each value bet found
- Supports JSON output with `--json` flag

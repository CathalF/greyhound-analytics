# Phase 3 Plan 1: Oddschecker Data Access Discovery Summary

**Successfully discovered oddschecker.com access patterns, URL structure, and complete data extraction strategy for greyhound racing odds**

## Accomplishments

- Manually explored oddschecker.com structure for greyhound racing
- Identified data access pattern: Main listing page at `/greyhounds` with race URLs following `/greyhounds/{track}/{time}/winner`
- Documented complete field mappings to Race/Dog/Odds models with CSS selectors and extraction algorithms
- Selected dog name matching strategy: Normalized string matching (lowercase, remove spaces/hyphens)
- Defined refresh strategy: Initial morning batch + continuous 5-minute polling for active races

## Files Created/Modified

- `research_notes_oddschecker.md` - Complete 300-line data access specification with:
  - URL patterns and navigation strategy
  - HTML structure and CSS selectors
  - Field extraction algorithms
  - Dog name matching implementation
  - Integration strategy with Phase 2 stats database
  - Sample data and testing notes

**Test Scripts**:
- `test_oddschecker_simple.py` - Confirmed site requires stealth (403 without)
- `test_oddschecker_stealth.py` - Verified stealth configuration works (200 status)
- `test_greyhound_urls.py` - Discovered working URL: `/greyhounds`
- `explore_race_details.py` - Navigated from listing to race cards
- `explore_single_race.py` - Extracted detailed race card structure

**Generated Files**:
- `oddschecker_home.png` - Home page screenshot
- `greyhound_page_0.png` - Greyhound listing page screenshot
- `race_card_detailed.png` - Individual race card screenshot with odds table
- `greyhound_listing.html` - Full HTML of listing page (536 race links found)
- `race_card_detailed.html` - Full HTML of race card with all data structures

## Decisions Made

### Architecture Decisions

**Dog name matching strategy: Normalized String Match**
- Rationale: Handles capitalization and spacing differences without false positives
- Implementation: Lowercase both names, remove spaces/hyphens/apostrophes, compare strings
- Example: "Rathbally Bolger" → "rathballybolger" matches "RATHBALLY BOLGER" → "rathballybolger"
- Fallback: If no match found, create new dog entry with race info but no stats

**Refresh frequency: Initial batch + 5-minute polling**
- Rationale: Balance real-time odds requirements with rate limiting constraints
- Implementation: Morning batch scrapes all today's races, separate process refreshes active races (starting within 2 hours) every 5 minutes
- Storage: Update latest odds via upsert (INSERT ... ON CONFLICT DO UPDATE)

**JavaScript rendering: Playwright required**
- Rationale: Stealth configuration is essential (site returns 403 without it), and Playwright handles both stealth and dynamic content
- Implementation: Use existing BaseScraper infrastructure from Phase 1, apply 3-second wait after page load for any dynamic content

### Data Access Pattern

**URL Structure Discovered**:
```
Listing page: https://www.oddschecker.com/greyhounds
Race page:    https://www.oddschecker.com/greyhounds/{track}/{time}/winner

Examples:
  https://www.oddschecker.com/greyhounds/harlow/18:11/winner
  https://www.oddschecker.com/greyhounds/millersfield/08:07/winner
```

**CSS Selectors**:
- Dogs: `tr[data-bname]` (6 rows = 6 dogs/traps)
- Dog name: `data-bname` attribute
- Odds cells: `[data-o]` selector
- Bookmaker: `data-bk` attribute
- Fractional odds: `data-o` attribute (e.g., "6/4", "9/2")
- Decimal odds: `data-odig` attribute (e.g., "2.5", "5.5")

**Field Mappings**:
- Track: Parse from URL or page title
- Time: Parse from URL (format "HH:MM")
- Distance: Regex search for `\d{3,4}m` pattern (may be NULL)
- Trap number: Row index + 1 (position in table)
- Dog name: `data-bname` attribute value
- Odds: Extract from `data-o` and `data-odig`, skip if value is "SP" (Starting Price)

## Issues Encountered

### Minor Issues (Resolved)

**403 Forbidden without stealth configuration**
- Issue: Direct access without playwright-stealth returns 403
- Impact: Cannot scrape without proper stealth setup
- Resolution: Applied playwright-stealth with `setup_stealth_page()` and browser launch args from Phase 1

**Rate limiting on rapid requests**
- Issue: Multiple rapid requests triggered 403 responses
- Impact: Batch scraping requires careful pacing
- Resolution: 2-second delays between requests (matches Phase 2 pattern)

**Unicode encoding errors in Windows console**
- Issue: Unicode checkmarks (✓, ✗) caused encoding errors in test scripts
- Impact: Script crashes when printing status messages
- Resolution: Replaced Unicode symbols with ASCII alternatives ([OK], [X])

**Closed races showing in initial tests**
- Issue: Morning races already finished (08:07, 08:28, etc.) showed as "Closed"
- Impact: Couldn't test with live odds initially
- Resolution: Found afternoon/evening races (18:11, 19:24, etc.) with active odds

### No Major Issues

- ✅ Stealth configuration successfully bypasses anti-bot protection
- ✅ All required data fields are present and extractable
- ✅ HTML structure is consistent and well-structured (table-based)
- ✅ Bookmaker codes are consistent across races
- ✅ Dog names match Phase 2 format (normalization will handle minor differences)
- ✅ Odds data includes both fractional and decimal formats
- ✅ Page loads are fast (~3 seconds including dynamic content)

## Sample Data Extracted

### Race Example

**URL**: `https://www.oddschecker.com/greyhounds/harlow/18:11/winner`

**Race Info**:
- Track: Harlow
- Time: 18:11
- Distance: (not displayed on race card, may need from greyhoundstats)

**Dogs** (6 total, typical for greyhound racing):
1. Rathbally Bolger (Trap 1)
2. Old Fort Sizzler (Trap 2)
3. Baran Maverick (Trap 3)
4. [Three more dogs in Traps 4-6]

**Sample Odds** (Rathbally Bolger):
- Bet365 (B3): 6/4 (2.5 decimal)
- Sky Bet (SK): 13/8 (2.63 decimal) - Best odds
- Paddy Power (PP): 13/8 (2.63 decimal) - Best odds
- Betfred (BF): 4/6 (1.71 decimal) - Worst odds
- William Hill (WH): SP (Starting Price - not yet available)
- Unibet (UN): SP
- [~20 more bookmakers with various odds or SP]

**Bookmaker Coverage**: ~26 bookmakers per race

**Odds Formats**:
- Fractional: 6/4, 9/2, 11/4, 5/1, etc.
- Decimal: 2.5, 5.5, 3.75, 6.0, etc.
- SP: Starting Price (odds TBD at race start)

## Integration with Phase 2

### Phase 2 Assets Available

- `BaseScraper` class with Playwright + stealth configuration
- `TokenBucketRateLimiter` (0.5 req/sec = 2-second delays)
- Dog stats database with 31+ dogs from greyhoundstats.co.uk
- Database models: Race, Dog, Odds (schema needs `odds` table addition)

### Integration Flow

**Step 1: Morning Batch Scrape**
1. Scrape `/greyhounds` listing page → get all today's races
2. For each race: scrape race card → extract dogs + odds
3. Create races in database
4. Match dog names against Phase 2 stats database (normalized comparison)
5. Update existing dogs with `race_id` and `trap_number`
6. Create new dogs for unmatched names (stats will be NULL)
7. Store all odds in new `odds` table

**Step 2: Continuous Refresh (every 5 minutes)**
1. Query database for active races (starting within next 2 hours)
2. Re-scrape each active race's odds
3. Upsert odds in database (update existing or insert new)
4. Log any significant odds changes

**Step 3: Value Identification (Phase 4)**
1. Query dogs with strong stats (high win rate, strong recent form)
2. Compare their current odds across bookmakers
3. Identify value bets (strong dogs with favorable odds)
4. Display in dashboard

## Next Steps

**Ready for Plan 03-02: Implement OddscheckerScraper**

Plan 03-02 will implement:
1. `OddscheckerScraper` class extending `BaseScraper`
2. Methods:
   - `get_todays_races()` → List of race URLs
   - `scrape_race(url)` → Race data with dogs and odds
   - `match_dog_name(oddschecker_name)` → Find matching dog in Phase 2 database
3. Database schema update:
   - Add `odds` table with columns: id, dog_id, bookmaker, fractional_odds, decimal_odds, timestamp
4. Integration with existing storage layer
5. Unit tests with sample HTML from research

Plan 03-03 will implement:
1. Batch scraper for initial morning load
2. Continuous refresh process for real-time odds updates
3. Error handling and retry logic
4. Logging and monitoring

---

**Plan Status**: ✅ COMPLETE
**Date Completed**: 2026-01-14
**Next Phase**: Plan 03-02 - Implement OddscheckerScraper

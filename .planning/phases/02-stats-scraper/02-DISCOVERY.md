# Phase 2: Stats Scraper - Discovery

**Researched:** 2026-01-13
**Phase Goal:** Implement reliable daily scraping of greyhound statistics
**Confidence:** MEDIUM

## Discovery Summary

After investigating greyhoundstats.co.uk and related sites, I've identified a **critical architectural decision** that affects this phase:

**Finding:** The original plan assumed greyhoundstats.co.uk provides upcoming race cards with dog statistics. However:
1. **greyhoundstats.co.uk** - Provides historical dog performance statistics (win rates, track preferences, ratings) but NOT upcoming race fixtures
2. **timeform.com / attheraces.com** - Have race cards with fixtures but returned 403 errors (anti-bot protection)
3. **oddschecker.com** - Will provide odds in Phase 3 and may also have race fixtures

**Two possible architectures:**

### Architecture A: Multi-Source Stats (Recommended)
- **Phase 2**: Scrape greyhoundstats.co.uk for dog profile/historical stats database
- **Phase 3**: Scrape oddschecker.com for BOTH odds AND race fixtures (dogs running today)
- **Logic**: Match dogs in today's races (from oddschecker) against historical stats database
- **Benefit**: Single scraper per phase, clear separation of concerns
- **Challenge**: Need to match dog names across sites (may have variations)

### Architecture B: Integrated Race Cards
- **Phase 2**: Find alternative race card source (attheraces.com, individual tracks)
- **Challenge**: attheraces/timeform have strong anti-bot (403 errors observed)
- **Challenge**: Individual track sites vary significantly (different HTML structures)
- **Benefit**: More complete data per dog per race

## Site Analysis

### greyhoundstats.co.uk Structure

**What it provides:**
- Individual dog race form and ratings
- Trainer statistics (graded/open races)
- Track statistics by trap
- Top 50 rankings (most wins, runs, etc.)
- Time/rating comparisons

**What it does NOT provide:**
- Upcoming race fixtures/cards
- Real-time odds
- Race schedules

**HTML Structure:**
- PHP-based site (URLs like `graded_averages2.php`)
- Traditional server-rendered HTML
- Search functionality for dog names
- No obvious CAPTCHA or aggressive anti-bot on homepage

**Sample URL patterns (inferred):**
```
https://greyhoundstats.co.uk/               # Homepage
https://greyhoundstats.co.uk/graded_averages2.php  # Stats page
Query params likely: ?dog=[name]&track=[name]&distance=[meters]
```

### oddschecker.com (Phase 3 preview)

**Expected to provide:**
- Real-time odds from multiple bookmakers
- Race cards with dog names, trap numbers, times
- Track information

**Note:** Not explored in Phase 2, but critical architectural dependency

## Data Flow Decision Point

**DECISION NEEDED BEFORE PLANNING:**

Which architecture should we implement?

**Option A (Recommended): Stats Database + Oddschecker Integration**
```
Phase 2: Build dog stats database from greyhoundstats.co.uk
  - Scrape top dogs, ratings, win rates, track preferences
  - Store in database indexed by dog name
  - Daily refresh to keep stats current

Phase 3: Scrape oddschecker for races + odds
  - Get today's race cards (dogs running)
  - Get odds for each dog
  - Match dog names against stats database
  - Identify value bets (good stats vs good odds)
```

**Option B: Find Race Card Source**
```
Phase 2: Scrape race cards from [TBD source]
  - Overcome anti-bot on timeform/attheraces
  - OR scrape individual track websites
  - Get fixtures with dog names
  - Enrich with greyhoundstats data

Phase 3: Add odds from oddschecker
  - Match against Phase 2 race data
```

## Recommendation

**Implement Architecture A** for these reasons:

1. **Clearer separation**: Phase 2 = stats, Phase 3 = odds+fixtures
2. **Single difficult scraper per phase**: Don't fight multiple anti-bot systems at once
3. **More sustainable**: Historical stats change slowly (daily batch OK), odds change rapidly (need real-time)
4. **Better value identification**: Rich historical stats database enables pattern analysis
5. **Oddschecker likely has fixtures anyway**: Most odds sites show race cards

## Phase 2 Scope (Architecture A)

**Goal:** Build a comprehensive dog statistics database

**Tasks:**
1. **Discover greyhoundstats.co.uk data access patterns**
   - Find dog search/listing pages
   - Identify individual dog profile URLs
   - Map available stats fields to our data model

2. **Implement greyhound stats scraper**
   - Subclass BaseScraper (from Phase 1)
   - Parse dog statistics pages
   - Extract: dog name, ratings, win rate, track preferences, recent form
   - Handle missing data gracefully

3. **Build stats storage layer**
   - Extend Dog model with stats fields
   - Create upsert logic (update existing, insert new)
   - Index by dog name for fast lookups

4. **Create daily batch job**
   - Scrape top N dogs or all active dogs
   - Update database
   - Log scraping stats (success/failure rate)

## Data Model Extension

Current `Dog` model from Phase 1:
```python
dog_id, name, race_id, trap_number, stats (JSONB), last_stats_update
```

**Phase 2 additions to `stats` JSONB:**
```json
{
  "rating": 45,              // greyhoundstats rating
  "win_rate": 0.23,         // percentage of wins
  "recent_form": "1-3-2-4-1",  // last 5 finishes
  "track_preferences": {
    "Sunderland": {"runs": 10, "wins": 3, "avg_finish": 2.1},
    "Nottingham": {"runs": 8, "wins": 1, "avg_finish": 3.4}
  },
  "distance_preferences": {
    "480m": {"runs": 12, "wins": 4},
    "540m": {"runs": 6, "wins": 0}
  },
  "trap_stats": {
    "1": {"runs": 3, "wins": 1},
    "2": {"runs": 4, "wins": 2}
  }
}
```

## Technical Challenges

1. **Finding data access pattern**: Need to discover how to systematically access dog data
   - Search functionality?
   - Listing pages?
   - Crawling track-by-track?

2. **Data completeness**: Some dogs may have limited stats

3. **Name matching**: Phase 3 will need to match "SUPERDOG" vs "Super Dog" variations

4. **Refresh strategy**: How often to update? Daily full refresh or incremental?

## Open Questions

1. **User confirmation needed**: Architecture A vs B?
2. **Scraping scope**: Top 100 dogs? Top 500? All active dogs?
3. **Storage**: Do we create separate `dog_stats` table or continue using JSONB in `dogs.stats`?

## Next Steps

1. **Decision checkpoint**: Confirm Architecture A
2. **Discovery task**: Manually explore greyhoundstats.co.uk to find data access patterns
3. **Plan Phase 2 execution**: Break into 2-3 plans with tasks

---

**Research Sources:**
- [Greyhound Stats UK](https://greyhoundstats.co.uk/)
- [Best Sites For Free Greyhound Racing Statistics](https://punter2pro.com/free-greyhound-racing-statistics-stats/)
- [Timeform Greyhound Racing](https://www.timeform.com/greyhound-racing/racecards)

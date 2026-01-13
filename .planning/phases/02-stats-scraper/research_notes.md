# Greyhoundstats.co.uk Data Access Research

**Date:** 2026-01-13
**Phase:** 02-stats-scraper
**Plan:** 02-01 (Data Access Discovery)

## Summary

Successfully explored greyhoundstats.co.uk and discovered a straightforward data access pattern using listing pages and individual dog profile URLs. The site has no aggressive anti-bot protection (no CAPTCHA observed with rate-limited requests) and provides comprehensive historical statistics for greyhounds.

## Key Findings

### 1. Site Structure

**Technology:**
- PHP-based server-rendered site
- Traditional HTML (no heavy JavaScript frameworks)
- Simple table-based layouts
- No obvious CAPTCHA or aggressive anti-bot on normal browsing

**Navigation Pattern:**
- Homepage: https://greyhoundstats.co.uk/
- Clear navigation menu with multiple entry points to dog data

### 2. How to Find Individual Dog Pages

**Method: Listing Pages → Individual Dog Profiles**

There are multiple listing pages that provide links to individual dog profiles:

#### Option A: Top Ratings Page (RECOMMENDED)
- **URL:** https://greyhoundstats.co.uk/top_ratings.php
- **Contains:** Links to top-rated dogs with recent performance
- **Link Pattern:** `complete_runner_stats.php?dog=<dog_name>`
- **Example Links Found:**
  - Proper Heiress → `complete_runner_stats.php?dog=Proper Heiress`
  - Vhagar → `complete_runner_stats.php?dog=Vhagar`
  - Stonepark Hoffa → `complete_runner_stats.php?dog=Stonepark Hoffa`

#### Option B: Top 50s Page
- **URL:** https://greyhoundstats.co.uk/top_50s.php
- **Contains:** Top 50 lists (most wins, runs, etc.)
- **Note:** Can filter by year and track

#### Option C: Graded/Open Greyhounds Pages
- **Graded:** https://greyhoundstats.co.uk/graded_greyhound_stats.php
- **Open:** https://greyhoundstats.co.uk/open_greyhound_stats.php
- **Contains:** Statistics for graded and open racing dogs

#### Option D: Search Functionality
- **URL:** https://greyhoundstats.co.uk/find_greyhound.php
- **Form Field:** `dogref` (text input)
- **Method:** Can search for specific dog by name
- **Use Case:** Good for targeted lookups, not bulk discovery

### 3. URL Pattern for Dog Profiles

**Pattern:** `https://greyhoundstats.co.uk/complete_runner_stats.php?dog=<dog_name>`

**Examples:**
- `complete_runner_stats.php?dog=Proper Heiress`
- `complete_runner_stats.php?dog=Vhagar`
- `complete_runner_stats.php?dog=Stonepark Hoffa`

**Notes:**
- Dog name is URL-encoded (spaces become `%20`)
- Case-sensitive (use exact name from listing pages)

### 4. Available Statistics on Dog Pages

#### Table 1: Summary Statistics
| Field | Example | Type |
|-------|---------|------|
| Runs | 32 | Integer |
| Wins | 23 | Integer |
| Win % | 71.87 | Float |

#### Table 2: Race History (Detailed)
| Field | Example | Description |
|-------|---------|-------------|
| Date | 13/12/2025 | Race date (DD/MM/YYYY) |
| Track | Hove | Track name |
| Trap | (empty in samples) | Trap number (1-6) |
| Dog | Proper Heiress | Dog name |
| Grade | OR1 | Grade (OR1, OR3, etc.) |
| Distance | 515m | Race distance |
| SP | 2/7F | Starting Price (F = Favourite) |
| Finish | 1 | Finishing position |
| Sectional | 4.31 | Sectional time |
| Actual Time | 29.39 | Actual race time |
| Going | N | Track condition (N=Normal, +30=slow, -30=fast) |
| Calc. Time | 29.39 | Calculated time (adjusted for going) |
| Chester Rating | 144 | Performance rating |
| Trainer | M A Wallis | Trainer name |
| Video | (link if available) | Video link |

### 5. Data Extraction Strategy

#### HTML Structure
- Dog profiles use table-based layouts
- **Table 1:** Navigation menu (ignore)
- **Table 2:** Summary stats (Runs, Wins, Win %)
- **Table 3:** Race history with all details

#### Parsing Approach
```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, 'html.parser')
tables = soup.find_all('table')

# Summary stats (Table 2)
summary_table = tables[1]
summary_rows = summary_table.find_all('tr')
headers = [cell.text.strip() for cell in summary_rows[0].find_all(['th', 'td'])]
data = [cell.text.strip() for cell in summary_rows[1].find_all(['th', 'td'])]
# Result: {'Runs': 32, 'Wins': 23, 'Win %': 71.87}

# Race history (Table 3)
race_table = tables[2]
race_rows = race_table.find_all('tr')
headers = [cell.text.strip() for cell in race_rows[0].find_all(['th', 'td'])]
# Parse each row into race data
```

### 6. Anti-Bot Behavior

**Testing Results:**
- ✅ No CAPTCHA observed during exploration
- ✅ No redirects or blocking with 2-second delays
- ✅ No aggressive anti-bot protection detected
- ✅ Successfully accessed multiple pages with rate limiting

**Recommended Rate Limiting:**
- **Minimum delay:** 2 seconds between requests (0.5 req/sec)
- **Suggested delay:** 2-3 seconds (safer, more respectful)
- Use TokenBucketRateLimiter (already implemented in Phase 1)

### 7. Field Mapping to Dog Model

Our Dog model from Phase 1:
```python
@dataclass
class Dog:
    dog_id: str
    name: str
    race_id: str
    trap_number: int
    stats: Dict[str, Any]  # JSONB field
    last_stats_update: Optional[datetime]
    created_at: datetime
```

**Mapping Strategy:**

The `stats` JSONB field will contain:
```json
{
  "runs": 32,
  "wins": 23,
  "win_rate": 71.87,
  "rating": 144,  // Latest Chester Rating
  "recent_form": [
    {
      "date": "2025-12-13",
      "track": "Hove",
      "trap": null,
      "grade": "OR1",
      "distance": "515m",
      "finish_position": 1,
      "sp": "2/7F",
      "sectional": "4.31",
      "actual_time": "29.39",
      "going": "N",
      "calc_time": "29.39",
      "rating": 144,
      "trainer": "M A Wallis"
    }
    // ... last 5-10 races
  ],
  "track_stats": {
    "Hove": {
      "runs": 5,
      "wins": 5,
      "win_rate": 100.0,
      "avg_rating": 135
    },
    "Nottingham": {
      "runs": 3,
      "wins": 2,
      "win_rate": 66.67,
      "avg_rating": 120
    }
  },
  "distance_stats": {
    "515m": {"runs": 5, "wins": 5},
    "500m": {"runs": 3, "wins": 2}
  },
  "grade_stats": {
    "OR1": {"runs": 8, "wins": 7}
  }
}
```

### 8. Sample URLs for Testing

**Dog Profiles:**
- https://greyhoundstats.co.uk/complete_runner_stats.php?dog=Proper%20Heiress
- https://greyhoundstats.co.uk/complete_runner_stats.php?dog=Vhagar
- https://greyhoundstats.co.uk/complete_runner_stats.php?dog=Stonepark%20Hoffa

**Listing Pages:**
- https://greyhoundstats.co.uk/top_ratings.php
- https://greyhoundstats.co.uk/graded_greyhound_stats.php

### 9. Handling Missing/Incomplete Data

**Observed Issues:**
- Trap number field is often empty in race history
- Video links not always present
- Some fields may have unexpected formats

**Handling Strategy:**
```python
# Use .get() with defaults
trap = cell.text.strip() or None
finish = int(cell.text.strip()) if cell.text.strip().isdigit() else None

# Validate before storing
if dog_name and runs is not None and wins is not None:
    # Safe to store
    pass
```

---

## DECISION CHECKPOINT

Based on exploration, I recommend the following data access strategy:

### RECOMMENDED: Listing-Crawl Approach

**Why:**
- Top Ratings page provides curated list of active, high-performing dogs
- Efficient: Discover 50-100+ dogs from one listing page
- Automatically focuses on relevant dogs (active, performing well)
- Can expand to other listing pages later

**Implementation Plan:**
1. Scrape Top Ratings page (https://greyhoundstats.co.uk/top_ratings.php)
2. Extract all dog profile links: `complete_runner_stats.php?dog=<name>`
3. For each dog link:
   - Navigate to profile page with rate limiting (2-sec delay)
   - Extract summary stats (runs, wins, win %)
   - Extract race history (last 10-20 races)
   - Calculate derived stats (track preferences, distance stats, etc.)
   - Store in Dog model with JSONB stats field

**Alternative Options Considered:**

1. **Search-Based:** Would require maintaining a list of dog names, slower, less discovery-friendly
2. **Hybrid:** Too complex for Phase 2, can add later if needed

---

## DATA EXTRACTION SPECIFICATION

### Step 1: Scrape Listing Page
**URL:** https://greyhoundstats.co.uk/top_ratings.php
**Extract:** All links matching pattern `complete_runner_stats.php?dog=*`
**CSS Selector:** `a[href*="complete_runner_stats.php"]`

### Step 2: Extract Dog Profile Data

**URL Pattern:** `complete_runner_stats.php?dog={dog_name}`

**HTML Selectors:**

```python
# Summary Stats
summary_table = soup.find_all('table')[1]
summary_data = {
    'runs': int(summary_table.find_all('td')[0].text.strip()),
    'wins': int(summary_table.find_all('td')[1].text.strip()),
    'win_rate': float(summary_table.find_all('td')[2].text.strip())
}

# Race History
race_table = soup.find_all('table')[2]
race_rows = race_table.find_all('tr')[1:]  # Skip header

for row in race_rows:
    cells = row.find_all('td')
    race = {
        'date': cells[0].text.strip(),
        'track': cells[1].text.strip(),
        'trap': cells[2].text.strip() or None,
        'dog': cells[3].text.strip(),
        'grade': cells[4].text.strip(),
        'distance': cells[5].text.strip(),
        'sp': cells[6].text.strip(),
        'finish': cells[7].text.strip(),
        'sectional': cells[8].text.strip(),
        'actual_time': cells[9].text.strip(),
        'going': cells[10].text.strip(),
        'calc_time': cells[11].text.strip(),
        'rating': cells[12].text.strip(),
        'trainer': cells[13].text.strip()
    }
```

### Step 3: Transform to Dog Model

```python
from datetime import datetime
from src.models.dog import Dog

# Generate dog_id from name (slug)
dog_id = dog_name.lower().replace(' ', '-')

# For Phase 2, use placeholder race_id (no races yet)
# Race integration happens in Phase 3 with oddschecker
race_id = 'standalone-stats'

# Store in Dog model
dog = Dog(
    dog_id=dog_id,
    name=dog_name,
    race_id=race_id,  # Placeholder for Phase 2
    trap_number=0,  # Unknown until race assignment in Phase 3
    stats={
        'runs': summary_data['runs'],
        'wins': summary_data['wins'],
        'win_rate': summary_data['win_rate'],
        'recent_form': recent_races[:10],  # Last 10 races
        'track_stats': calculate_track_stats(all_races),
        'distance_stats': calculate_distance_stats(all_races),
        'grade_stats': calculate_grade_stats(all_races),
        'latest_rating': all_races[0]['rating'] if all_races else None
    },
    last_stats_update=datetime.now(),
    created_at=datetime.now()
)
```

### Step 4: Derived Statistics Calculation

```python
def calculate_track_stats(races):
    """Calculate performance by track."""
    track_stats = {}
    for race in races:
        track = race['track']
        if track not in track_stats:
            track_stats[track] = {'runs': 0, 'wins': 0, 'ratings': []}

        track_stats[track]['runs'] += 1
        if race['finish'] == '1':
            track_stats[track]['wins'] += 1

        if race['rating'] and race['rating'].isdigit():
            track_stats[track]['ratings'].append(int(race['rating']))

    # Calculate averages
    for track, stats in track_stats.items():
        stats['win_rate'] = (stats['wins'] / stats['runs'] * 100) if stats['runs'] > 0 else 0
        stats['avg_rating'] = sum(stats['ratings']) / len(stats['ratings']) if stats['ratings'] else 0
        del stats['ratings']  # Don't store raw list

    return track_stats

def calculate_distance_stats(races):
    """Calculate performance by distance."""
    # Similar pattern to track_stats
    pass

def calculate_grade_stats(races):
    """Calculate performance by grade."""
    # Similar pattern to track_stats
    pass
```

---

## SCRAPING SCOPE

### Initial Target
- **Quantity:** Top 100-200 dogs from Top Ratings page
- **Why:** Focuses on active, high-performing dogs most likely to appear in upcoming races
- **Refresh:** Daily full refresh (stats change slowly, no need for real-time)

### Storage Requirements
- ~200 dogs × ~10KB per dog (with race history) = ~2MB total
- Well within database limits

### Refresh Strategy
- **Daily batch job:** Run once per day (e.g., 6 AM)
- **Full refresh:** Update all dogs in database
- **Upsert logic:** Update existing records, insert new ones
- **Indexing:** By dog name for fast lookups in Phase 3

---

## NEXT STEPS FOR PLAN 02-02 (Implementation)

1. Create `GreyhoundStatsScraper` class extending `BaseScraper`
2. Implement listing page scraper to discover dog URLs
3. Implement dog profile parser with BeautifulSoup
4. Create derived stats calculation functions
5. Implement database upsert logic
6. Create daily batch job scheduler
7. Add error handling and logging
8. Test with sample dogs
9. Run full scrape of Top 100 dogs

---

## FILES GENERATED DURING EXPLORATION

- `homepage_screenshot.png` - Homepage visual reference
- `homepage_content.html` - Homepage HTML
- `greyhound_search.html` - Search page structure
- `top_50s.html` - Top 50s listing page
- `top_ratings.html` - Top ratings listing page
- `graded_greyhounds.html` - Graded dogs page
- `dog_profile_proper_heiress.html` - Sample dog profile
- `dog_profile_proper_heiress.png` - Visual reference
- `dog_profile_vhagar.html` - Second sample
- `dog_profile_stonepark_hoffa.html` - Third sample
- `dog_profile_*.json` - Structured analysis data

---

**Research Status:** ✅ COMPLETE
**Ready for Implementation:** YES
**Next Plan:** 02-02 (Implement Dog Stats Scraper)

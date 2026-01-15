# Oddschecker.com Data Access Research Notes

**Date**: 2026-01-14
**Purpose**: Document oddschecker.com structure for greyhound racing odds scraping

## Summary

Oddschecker.com is accessible with proper stealth configuration (Playwright + playwright-stealth). The site has a clear structure for greyhound racing with a main listing page showing all tracks/races, and individual race pages with detailed odds comparison tables.

## Access Strategy

### Anti-Bot Protection

- **Without stealth**: Returns 403 Forbidden
- **With stealth**: Returns 200 OK
- **Required configuration**:
  - Playwright with chromium browser
  - playwright-stealth library (Stealth class with `apply_stealth_async()`)
  - Disable automation signals: `--disable-blink-features=AutomationControlled`
  - Realistic user agent and viewport
- **Rate limiting**: 2-second delays between requests (matches Phase 2 pattern)
- **Headless mode**: Works in both headless and non-headless modes

### URL Patterns

#### 1. Main Greyhound Listing Page

**URL**: `https://www.oddschecker.com/greyhounds`

**Purpose**: Shows all UK & Ireland greyhound tracks with today's race times

**Structure**:
- Lists multiple tracks (Millersfield, Brushwood, Harlow, Kilkenny, Monmore, Nottingham, Towcester, Doncaster, Hove, etc.)
- Shows race times for each track in chronological order
- Each race time is a clickable link to the race card
- Tabs: "GREYHOUNDS HOME", "ANTE-POST", "FAST RESULTS"

**Race Link Pattern**:
```
/greyhounds/{track-name}/{time}/winner
```

Examples:
- `/greyhounds/harlow/18:11/winner`
- `/greyhounds/millersfield/08:07/winner`
- `/greyhounds/brushwood/13:16/winner`

**Full URL**:
```
https://www.oddschecker.com/greyhounds/{track}/{time}/winner
```

#### 2. Individual Race Card Page

**URL Pattern**: `https://www.oddschecker.com/greyhounds/{track}/{time}/winner`

**Example**: `https://www.oddschecker.com/greyhounds/harlow/18:11/winner`

**Page Title Format**: `{Track} {Time} Betting Odds- Winner | Greyhounds | Oddschecker`

Example: "Harlow 18:11 Betting Odds- Winner | Greyhounds | Oddschecker"

## Data Structure

### Race Card HTML Structure

The main odds comparison table uses a table structure with:

#### Table Rows (Dogs/Runners)

Each dog is represented by a `<tr>` element with:

**Key Attributes**:
```html
<tr class="diff-row evTabRow bc"
    data-bid="27196317638"
    data-bname="Rathbally Bolger"
    data-best-bks="SK,PP"
    data-hcap=""
    data-stall=""
    data-initial-odds-state="..."
    data-best-dig="2.63"
    data-best-dig-ea="2.63"
    data-best-dig-wo="1.71">
```

**Attributes Explained**:
- `data-bid`: Unique bet/selection ID for this dog in this race
- `data-bname`: Dog name (exact format from oddschecker)
- `data-best-bks`: Comma-separated bookmaker codes offering best odds
- `data-best-dig`: Best decimal odds available
- `data-initial-odds-state`: Encoded string with all bookmaker odds (see below)

**CSS Selector**:
```css
tr[data-bname]
```

This reliably selects all dog rows in the race (typically 6 rows for 6 dogs/traps).

### Odds Data Structure

#### Individual Odds Cells

Each bookmaker's odds for each dog is in a `<td>` element with `data-o` attribute:

```html
<td class="bc bs oc"
    data-bk="B3"
    data-odig="2.5"
    data-o="6/4"
    data-hcap=""
    data-fodds="2.38"
    data-best-ew="false"
    data-best-wo="false"
    data-ew-denom="4"
    data-ew-places="2">
  <a>6/4</a>
</td>
```

**Attributes**:
- `data-bk`: Bookmaker code (e.g., "B3", "WH", "UN", "FR", "PP", "SK", "BF")
- `data-o`: Fractional odds (e.g., "6/4", "9/2", "11/4", "SP")
- `data-odig`: Decimal odds (e.g., "2.5", "5.5", "3.75")
- `data-fodds`: Alternative decimal odds format
- **Note**: "SP" means "Starting Price" - odds not yet available (bookmaker will offer SP at race start)

**CSS Selector for all odds**:
```css
[data-o]
```

This selects all odds cells in the table (156 found in test = 26 bookmakers × 6 dogs).

### Extracting Race Information

#### Track Name and Time

From page title: `Harlow 18:11 Betting Odds- Winner`

Can also be found in `<h1>` tag.

**Extraction**:
```python
title = await page.title()
# Parse: "{Track} {Time} Betting Odds- Winner | Greyhounds | Oddschecker"
parts = title.split(" Betting Odds")[0]  # "Harlow 18:11"
track, time = parts.rsplit(" ", 1)  # track="Harlow", time="18:11"
```

#### Distance

**Pattern**: Typically shown as "500m", "380m", "695m" somewhere in the page content.

**Extraction**: Use regex to find patterns like `\d{3,4}m`

**Note**: Not always prominently displayed - may need to check multiple locations or scrape from greyhoundstats.co.uk instead (Phase 2 data likely has track distances).

#### Dogs and Trap Numbers

**Trap numbers**: Inferred from row position (1-6) or from trap color coding.

**Trap Color Mapping** (typical greyhound racing colors):
1. Red
2. Blue
3. White
4. Black
5. Orange
6. Black/White stripes (sometimes Green)

**Note**: Oddschecker uses color-coded columns. Trap number = row index + 1.

**Extraction**:
```python
soup = BeautifulSoup(html, 'html.parser')
dog_rows = soup.select('tr[data-bname]')

dogs = []
for i, row in enumerate(dog_rows, start=1):
    dog_name = row.get('data-bname')
    trap_number = i  # Trap 1-6 based on position
    dogs.append({
        'name': dog_name,
        'trap': trap_number,
        'bet_id': row.get('data-bid')
    })
```

#### Odds by Bookmaker

**Extraction**:
```python
# For each dog row
for dog_row in dog_rows:
    dog_name = dog_row.get('data-bname')

    # Find all odds cells in this row
    odds_cells = dog_row.select('[data-o]')

    for cell in odds_cells:
        bookmaker = cell.get('data-bk')
        fractional_odds = cell.get('data-o')
        decimal_odds = cell.get('data-odig')

        if fractional_odds != 'SP':  # Skip Starting Price
            odds.append({
                'dog_name': dog_name,
                'bookmaker': bookmaker,
                'fractional': fractional_odds,
                'decimal': float(decimal_odds)
            })
```

### Bookmaker Codes

Common codes found:
- `B3`: Bet365
- `WH`: William Hill
- `UN`: Unibet
- `FR`: Betfair
- `EE`: (Unknown)
- `SX`: (Unknown)
- `LD`: Ladbrokes
- `EP`: (Unknown)
- `VC`: (Unknown)
- `KN`: (Unknown)
- `BY`: Boylesports
- `OE`: (Unknown)
- `PP`: Paddy Power
- `SK`: Sky Bet
- `BF`: Betfred
- `QN`: QuinnBet
- And many more (~26 bookmakers total)

**Note**: May need to build a mapping from bookmaker codes to full names, or store codes as-is.

## Dog Name Matching Strategy

### Challenge

Dog names from oddschecker may not exactly match greyhoundstats.co.uk names due to:
- Capitalization differences
- Spacing/hyphen differences
- Abbreviations

### Recommended Approach: Normalized String Match

**Algorithm**:
1. Convert both names to lowercase
2. Remove all spaces, hyphens, and apostrophes
3. Compare resulting strings

**Example**:
```python
def normalize_dog_name(name):
    """Normalize dog name for matching"""
    return name.lower().replace(' ', '').replace('-', '').replace("'", '')

# Matching
oddschecker_name = "Rathbally Bolger"
stats_name = "RATHBALLY BOLGER"

if normalize_dog_name(oddschecker_name) == normalize_dog_name(stats_name):
    # Match found
```

**Pros**:
- Handles capitalization differences
- Handles spacing/hyphen variations
- Fast and simple
- No false positives (unlike fuzzy matching)

**Cons**:
- Won't handle significant spelling differences or abbreviations
- May miss matches if names differ substantially

**Fallback**: If no match found, log warning and create new dog entry (will have race_id but no stats).

## Data Flow Integration (Phase 2 → Phase 3)

### Current State (After Phase 2)

- `dogs` table has 31+ dogs with stats from greyhoundstats.co.uk
- Dog names stored in `dogs.name` field
- `dogs.race_id` is NULL (not linked to races yet)
- `dogs.trap_number` is NULL

### Phase 3 Integration

**Step 1: Scrape oddschecker for today's races**

```python
# Pseudo-code
races = []

# Get race listing
page.goto("https://www.oddschecker.com/greyhounds")
race_links = soup.select('a[href^="/greyhounds/"]')

for link in race_links:
    if re.match(r'/greyhounds/\w+/\d{2}:\d{2}/winner', link['href']):
        races.append({
            'url': f"https://www.oddschecker.com{link['href']}",
            'track': extract_track(link['href']),
            'time': extract_time(link['href'])
        })
```

**Step 2: For each race, extract dogs and odds**

```python
for race in races:
    page.goto(race['url'])

    # Create race in database
    race_id = db.create_race(
        track=race['track'],
        time=race['time'],
        distance=extract_distance(page)  # or NULL
    )

    # Extract dogs
    dog_rows = soup.select('tr[data-bname]')

    for i, row in enumerate(dog_rows, start=1):
        oddschecker_name = row.get('data-bname')
        trap = i

        # Match against Phase 2 stats database
        dog = db.find_dog_by_name(oddschecker_name)

        if dog:
            # Update existing dog with race info
            db.update_dog(
                dog_id=dog.id,
                race_id=race_id,
                trap_number=trap
            )
        else:
            # Create new dog (stats unknown, but in a race)
            dog = db.create_dog(
                name=oddschecker_name,
                race_id=race_id,
                trap_number=trap,
                stats=None  # No stats available yet
            )

        # Extract odds for this dog
        odds_cells = row.select('[data-o]')
        for cell in odds_cells:
            if cell.get('data-o') != 'SP':
                db.create_odds(
                    dog_id=dog.id,
                    bookmaker=cell.get('data-bk'),
                    fractional=cell.get('data-o'),
                    decimal=float(cell.get('data-odig'))
                )
```

**Step 3: Value bet identification** (Phase 4)

Compare dogs with strong stats (Phase 2) against favorable odds (Phase 3).

## Refresh Strategy

### Real-Time Odds Updates

**Requirement** (from ROADMAP): "Real-time odds refresh needed (every few minutes)"

**Recommended Strategy**:

1. **Initial scrape**: Morning batch job scrapes all today's races (like Phase 2 batch scraper)
2. **Continuous updates**: Separate process polls active races every 2-5 minutes
3. **Race filtering**: Only refresh races starting within next 2 hours (avoid refreshing old/distant races)
4. **Database upsert**: Update odds in database (INSERT ... ON CONFLICT DO UPDATE)

**Implementation**:
```python
# Pseudo-code for continuous refresh
while True:
    now = datetime.now()

    # Get active races (starting within next 2 hours)
    active_races = db.get_races_between(
        now,
        now + timedelta(hours=2)
    )

    for race in active_races:
        # Re-scrape this race
        refresh_race_odds(race)
        await asyncio.sleep(2)  # Rate limiting

    # Wait before next refresh cycle
    await asyncio.sleep(300)  # 5 minutes
```

**Storage Strategy**:
- Store latest odds only (not historical odds)
- OR: Store odds with timestamps for trend analysis (optional enhancement)

## JavaScript Rendering

**Finding**: Oddschecker loads most content server-side. Odds are present in initial HTML.

**Playwright still needed** for:
1. Anti-bot stealth configuration
2. Realistic browser fingerprint
3. Dynamic content (if any odds load via JS)

**Wait strategy**:
```python
await page.goto(url)
await asyncio.sleep(3)  # Wait for any dynamic content to load
```

## Anti-Bot Behavior Observations

### Working Conditions

- ✅ Stealth configuration applied
- ✅ 2-second delays between requests
- ✅ Realistic user agent
- ✅ Single browser session (avoid creating many browsers)

### Failure Conditions

- ❌ No stealth: 403 Forbidden
- ❌ Rapid requests without delays: 403 Forbidden
- ❌ Direct access to race URLs without visiting listing first: Sometimes 403 (not always)

### Best Practice

1. Start with listing page: `https://www.oddschecker.com/greyhounds`
2. Wait 2 seconds
3. Navigate to individual races with 2-second delays between each
4. Reuse same browser session for batch scraping

## Field Mappings to Database Models

### Race Model

From `src/models/race.py`:

```python
class Race:
    id: int
    track: str          # From URL or page title
    time: str           # From URL (format: "HH:MM")
    distance: str       # From page content (e.g., "500m") - optional
    created_at: datetime
```

**Extraction**:
- `track`: Parse from URL `/greyhounds/{track}/{time}/winner` or page title
- `time`: Parse from URL or page title
- `distance`: Regex search page content for `\d{3,4}m` pattern (may be NULL)

### Dog Model (updates to existing dogs)

From `src/models/dog.py`:

```python
class Dog:
    id: int
    name: str           # From data-bname attribute
    race_id: int        # Foreign key to races table (update from NULL)
    trap_number: int    # Position in race (1-6) - update from NULL
    stats: dict         # From Phase 2 (greyhoundstats.co.uk) - already populated
    created_at: datetime
    updated_at: datetime
```

**Extraction**:
- `name`: `tr[data-bname]` attribute
- `trap_number`: Row index + 1 (first row = trap 1, second row = trap 2, etc.)
- `race_id`: Link to race created in Step 2

### Odds Model

**New table needed** (not yet defined in Phase 2):

```python
class Odds:
    id: int
    dog_id: int             # Foreign key to dogs table
    bookmaker: str          # Bookmaker code (e.g., "B3", "WH", "PP")
    fractional_odds: str    # E.g., "6/4", "9/2", "11/4"
    decimal_odds: float     # E.g., 2.5, 5.5, 3.75
    timestamp: datetime     # When these odds were scraped
```

**Extraction**:
- `dog_id`: Matched dog from database
- `bookmaker`: `data-bk` attribute from `<td>`
- `fractional_odds`: `data-o` attribute (skip if "SP")
- `decimal_odds`: `data-odig` attribute parsed as float
- `timestamp`: Current time when scraped

## Sample Data

### Sample Race

**URL**: `https://www.oddschecker.com/greyhounds/harlow/18:11/winner`

**Dogs** (6 total):
1. Rathbally Bolger (Trap 1)
2. Old Fort Sizzler (Trap 2)
3. Baran Maverick (Trap 3)
4. (3 more dogs - Trap 4-6)

**Sample Odds** (Rathbally Bolger):
- Bet365 (B3): 6/4 (2.5 decimal)
- Sky Bet (SK): 13/8 (2.63 decimal)
- Paddy Power (PP): 13/8 (2.63 decimal)
- Betfred (BF): 4/6 (1.71 decimal)
- William Hill (WH): SP
- Unibet (UN): SP
- Many more (~26 bookmakers total)

## Testing Notes

**Test Scripts Created**:
- `test_oddschecker_simple.py`: Basic access test (no stealth) → 403
- `test_oddschecker_stealth.py`: Access with stealth → 200 ✓
- `test_greyhound_urls.py`: Find working greyhound URL → Found `/greyhounds` ✓
- `explore_race_details.py`: Navigate from listing to race → Some 403 issues
- `explore_single_race.py`: Direct race access with stealth → 200 ✓

**Files Generated**:
- `oddschecker_home.png`: Screenshot of home page
- `greyhound_page_0.png`: Screenshot of greyhound listing page
- `race_card_detailed.png`: Screenshot of individual race card
- `greyhound_listing.html`: Full HTML of listing page
- `race_card_detailed.html`: Full HTML of race card page

## Next Steps for Implementation (Plan 03-02)

1. Create `OddscheckerScraper` class extending `BaseScraper`
2. Implement `get_todays_races()` method:
   - Navigate to `/greyhounds`
   - Extract all race links with track/time
   - Return list of race URLs
3. Implement `scrape_race(url)` method:
   - Navigate to race URL
   - Extract track, time, distance
   - Extract dogs with trap numbers
   - Extract odds for each dog/bookmaker pair
   - Return structured data
4. Implement dog name matching against Phase 2 database
5. Create database schema for `odds` table
6. Implement upsert logic for races, dogs, and odds
7. Create batch scraper for initial load (morning job)
8. Create refresh scraper for real-time updates (every 5 minutes)

## Decision: Dog Name Matching Strategy

**Selected**: Normalized String Match

**Rationale**:
- Simple and fast
- No false positives
- Handles common formatting differences (capitalization, spacing, hyphens)
- Suitable for most dog name variations between the two sites

**Implementation**: See "Dog Name Matching Strategy" section above.

---

**Research Complete**: ✅
**Date**: 2026-01-14
**Ready for**: Plan 03-02 (Implement OddscheckerScraper)

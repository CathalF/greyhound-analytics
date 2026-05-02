# Greyhound Analytics

A Flask web application that scrapes live greyhound race data — race cards, bookmaker odds, dog statistics, and results — then applies a weighted multi-factor algorithm to surface value betting opportunities before each race. The dashboard shows upcoming races for the next four hours, flags dogs where the implied probability from the odds underestimates their historical win rate, and tracks bet outcomes with ROI reporting over time.

🚀 **Live demo:** coming soon

## Stack

- **Python 3.10+** / **Flask 2.3+** — server-side rendered Jinja2 templates + REST API
- **Playwright 1.48** + **playwright-stealth** — headless Chromium scraping with anti-detection
- **BeautifulSoup4** — HTML parsing for race cards and results
- **PostgreSQL** + **psycopg2-binary** — primary datastore with a `ThreadedConnectionPool` (min 1, max 10 connections)
- **APScheduler 3.10** — background job scheduling (results collection, outcome updates, auto-picking)
- **cachetools** — thread-safe TTL caching for pattern data and value scores
- **tenacity** — retry logic with exponential backoff on scrape failures
- **aiohttp** — async HTTP for non-browser requests
- **Flask-Compress** — gzip response compression (configurable algorithm, level, and min-size)
- **PyYAML** — centralised configuration via `config.yaml`

## Why this project

I built this as a personal project to work on something end-to-end that I actually cared about finishing. Greyhound racing is a well-structured domain: races happen every few minutes, every outcome is recorded, and the bookmaker market is inefficient enough that a historical win rate vs. implied probability comparison surfaces real signal. I wanted to go past a basic CRUD app and build a real scraping pipeline, a scoring algorithm I had to reason about carefully, and a background automation loop that keeps everything live without manual intervention.

## What it does

- Scrapes today's greyhound race cards from Sporting Life: grades (A1–A11, D, S, OR, Hcp), distances, trap draws, and race times
- Scrapes odds from Oddschecker across six bookmakers: Bet365, William Hill, Paddy Power, Sky Bet, Betfred, Betway
- Scrapes per-dog statistics from GreyhoundStats: overall win rate, track-specific win rates, distance-specific win rates, grade-specific win rates, and last 10 race form with positions
- Scrapes race results from Sporting Life to resolve pending bets
- Scores every dog in every upcoming race using a nine-factor weighted algorithm and surfaces those above a configurable threshold (default 1.25)
- Auto-picks the top-scoring dog per race within a 30-minute lookahead window, assigns a confidence-based stake (£10 / £20 / £30), and records the pick for outcome tracking
- Runs a background scheduler that collects results every six minutes, updates bet outcomes, and runs the auto-picker every five minutes
- Exposes a REST API with 16 JSON endpoints for race data, value scores, scheduler management, and auto-pick stats
- Renders a dashboard, per-race detail pages, bet history with ROI stats, and a pattern analysis page (trap bias, time-of-day ROI, track performance by value score bucket)

## Architecture

```
Sporting Life ───────→ SportingLifeScraper ──┐
Oddschecker ──────────→ OddscheckerScraper ──┼──→ PostgreSQL
GreyhoundStats ───────→ GreyhoundStatsScraper┘        │
Sporting Life Results → ResultsScraper ───────────────┘
                                                       │
                                                Value Engine
                                            (9-factor scoring)
                                                       │
                                  ┌────────────────────┼──────────────────┐
                                  ↓                    ↓                  ↓
                             Dashboard              /api/*           APScheduler
                           (Jinja2 HTML)         (JSON REST)     (background jobs)
```

**Key design decisions:**

- **Token bucket rate limiting, not fixed-window.** The `TokenBucketRateLimiter` allows short bursts (capacity = 5 tokens) while maintaining the configured average rate. A fixed-window approach would either be too aggressive against sites that allow short bursts, or too conservative on pages that don't penalise short request clusters.

- **`playwright-stealth` rather than hand-rolled fingerprinting.** The library patches navigator, WebGL, and canvas APIs that bot-detection scripts query. Writing and maintaining those patches manually is fragile; using the library keeps the evasion current as detection techniques evolve.

- **Dog stats stored as `JSONB` in the `dogs` table.** GreyhoundStats returns nested track/distance/grade breakdowns per dog. Storing this as a typed JSONB column avoids a normalised schema that would require multi-table joins on every value calculation, and PostgreSQL's JSONB operators still make the data queryable. The tradeoff is that filtering across dogs by specific stat values is less efficient than normalised columns would be.

- **Favourite strength applied as a final multiplier, not a weighted component.** When a race has a 1.20 odds-on favourite, discounting a longshot's score in proportion to their odds changes the fundamental viability of the bet — not just the size of the score. Folding it into the weighted sum would let other factors partially offset it, which would produce misleading results.

- **Config-driven factor weights via `config.yaml`.** All nine factor weights, both scoring thresholds, and all scheduler intervals are in `config.yaml`. I can tune the algorithm or change job cadences without touching Python. Weights are normalised at runtime to account for the favourite-strength factor being excluded from the weighted sum.

## Value scoring algorithm

Every dog in an upcoming race gets a score:

```
pre_fav_score = Σ (base_score × factor_i × weight_i) / Σ weight_i
final_score   = pre_fav_score × favourite_strength_multiplier
```

The nine factors and their default weights:

| Factor | Weight | What it measures |
|---|---|---|
| Base value | 25% | `win_rate / implied_probability` — the core signal |
| Form | 15% | Wins in last 5 races: 3+ = ×1.15, 0 = ×0.85; improving/declining trend ±5% |
| Class movement | 15% | +7% per grade dropped, −7% per grade risen; −20% cross-category (D→A/S) |
| Track | 10% | Dog's win rate at this track vs overall, capped ×0.5–2.0 |
| Distance | 10% | Dog's win rate at this distance (±20m tolerance, min 3 runs) vs overall |
| Grade | 10% | Dog's win rate at this specific grade vs overall (min 2 runs) |
| Trap bias | 5% | Historical trap win rate vs expected 16.67%; enhanced ±15% in Hcp races (T1 to T6 linear scale) |
| Time of day | 5% | Morning/afternoon/evening slot ROI vs average ROI (min 10 samples) |
| Favourite strength | ×multiplier | Up to −40% discount when there is a dominant favourite (sub-1.30 odds) combined with a longshot (>10 odds) |

A score ≥ 1.25 is flagged as a value bet. A score ≥ 1.50 triggers auto-picking.

**Worked example:** A dog with a 30% win rate at decimal odds of 5.0 has a base score of `0.30 / 0.20 = 1.50`. With strong recent form (+15%) and neutral trap/time factors, the weighted composite might reach 1.55. If the race favourite is at 1.80 (no dominant favourite), no discount applies. Final score: 1.55 — auto-pick territory.

## API overview

All JSON endpoints are prefixed `/api`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/races` | Upcoming races, paginated (`limit`, `offset`, `hours_ahead`) |
| GET | `/api/race/<id>` | Race detail with dogs and odds |
| GET | `/api/value-bets` | Value bets across upcoming races, filterable by `min_score` |
| GET | `/api/race/<id>/value` | Full nine-factor breakdown for every dog in one race |
| GET | `/api/value/summary` | Aggregate betting ROI, win rate, streaks, best/worst tracks |
| GET | `/api/filters/options` | Available tracks, grades, distances for UI filter dropdowns |
| GET | `/api/races/batch` | Multiple races in one request (max 50 IDs) |
| GET | `/api/scheduler/status` | Running jobs and next fire times |
| GET | `/api/scheduler/history` | Last N job executions with success/error |
| POST | `/api/scheduler/trigger/<job_id>` | Run a job immediately |
| POST | `/api/scheduler/pause/<job_id>` | Pause a job |
| POST | `/api/scheduler/resume/<job_id>` | Resume a paused job |
| GET | `/api/auto-picks` | Recent auto-picked bets with outcomes |
| GET | `/api/auto-picks/stats` | Win rate and ROI broken down by confidence level |
| POST | `/api/auto-picks/trigger` | Run the auto-picker now |
| POST | `/api/results/fetch` | Scrape and store latest results immediately |
| POST | `/api/race/<id>/refresh-odds` | Re-scrape Oddschecker odds for one specific race |

HTML pages: `/` (dashboard), `/race/<id>` (detail), `/bet-history`, `/patterns`.

## Highlights

- 9-factor weighted scoring algorithm with all weights and thresholds configurable in `config.yaml` without code changes
- Four concrete scraper classes (Sporting Life, Oddschecker, GreyhoundStats, Results) all extending one `BaseScraper` abstract class — shared retry logic, stealth setup, and rate limiting; subclasses only implement `parse()`
- Background scheduler with `coalesce=True` and `max_instances=1` — misfired jobs don't pile up on restart or slow machine
- Thread-safe TTL caching with `cachetools.TTLCache` and explicit `Lock()`: pattern data cached 30 minutes, value scores cached 5 minutes per dog/race/odds combination
- Batch DB queries in `get_all_value_bets`: 2 queries total for all races + all odds regardless of how many races are upcoming (previously 2 + 3N queries)
- `tenacity` retry with exponential backoff (2–10s, max 3 attempts) on all scrape calls — not a manual sleep loop

## Getting started

**Prerequisites:** Python 3.10+, a running PostgreSQL instance (local or hosted), Playwright browsers installed.

```bash
# Clone
git clone https://github.com/CathalF/greyhound-analytics.git
cd greyhound-analytics

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright's Chromium browser
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL to your PostgreSQL connection string

# Apply the database schema
psql $DATABASE_URL -f src/storage/schema.sql

# Start the app
python -m flask --app src/app.py run --port 5000
```

The dashboard is at `http://localhost:5000`. The background scheduler starts automatically. To populate initial data, trigger the scrapers via the API (`POST /api/results/fetch`) or run the full scraper script:

```bash
python src/full_scraper.py
```

## Environment variables

**Required:**

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/greyhound` |

**Optional (sensible defaults in `config.yaml`):**

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret — change this in production | `dev-secret-key-change-in-production` |
| `FLASK_DEBUG` | Enable Flask debug mode | `true` |
| `SMTP_SERVER` | SMTP server for email alerts | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USERNAME` | SMTP authentication username | — |
| `SMTP_PASSWORD` | SMTP authentication password | — |
| `EMAIL_FROM` | From address for alert emails | `alerts@greyhound-analytics.local` |

Email alert variables are only needed if you enable `alerts.email.enabled: true` in `config.yaml`. All algorithm weights, scheduler intervals, caching TTLs, and staking amounts are configured in `config.yaml`, not environment variables.

## Testing

Two integration test scripts test the scrapers against the live sites:

```bash
# Test Sporting Life grade scraper
python test_grade_scraper.py

# Test GreyhoundStats dog stats scraper
python test_stats_scraper.py
```

These are manual integration scripts — they print structured output showing what was extracted and flag if the page structure appears to have changed.

## What I'd do differently

**No automated test suite.** The two test scripts need a live internet connection and hit real sites. I'd replace them with a pytest suite using recorded HTML fixtures so the parsing logic is testable offline and in CI. The value scoring algorithm has enough conditional branches (nine factors, each with their own data availability checks and cap logic) to warrant dedicated unit tests per factor function.

**Rate limiter is per-instance, not shared.** Each `BaseScraper` subclass creates its own `TokenBucketRateLimiter`. When the scheduler runs multiple scrapers concurrently, each has its own independent token bucket, so the actual combined request rate is `N × configured_rate`. A shared singleton rate limiter passed in at the application level would correctly enforce the intended total rate.

**No `docker-compose`.** Setup requires a running Postgres instance, manual schema application, and `playwright install chromium`. A `docker-compose.yml` with a Postgres service would collapse that to `docker compose up`, which matters if someone else tries to run this.

**Factor weights aren't validated at startup.** The algorithm normalises by dividing by the actual sum of weights, so a misconfigured `config.yaml` won't crash — it'll silently produce scores that are numerically consistent but not comparable to the documented thresholds (1.25, 1.50). A one-line assertion at startup that `abs(sum(weights.values()) - 1.0) < 0.01` would catch this.

**`stats` JSONB has no per-stat indexes.** The current read pattern (fetch one dog, extract stats) works fine. But any future query like "find all dogs with a 500m win rate above 25%" requires a full table scan with a PostgreSQL JSON operator expression. If cross-dog stat queries become needed, extracting the most-queried fields into typed columns would be the right next step.

## Status

Personal project, built November 2025 – May 2026. Scraping pipeline, value-scoring engine, and background automation are complete and running live. Active development.

## Screenshots

<!-- TODO: add screenshots -->

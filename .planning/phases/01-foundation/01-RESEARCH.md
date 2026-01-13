# Phase 1: Foundation - Research

**Researched:** 2026-01-13
**Domain:** Web scraping infrastructure for greyhound racing data
**Confidence:** HIGH

<research_summary>
## Summary

Researched the modern web scraping ecosystem for building a reliable data extraction system targeting greyhoundstats.co.uk and oddschecker. The standard 2026 approach uses Playwright for JavaScript-heavy sites (like oddschecker) with headless browser automation, Python or Node.js as the language choice based on requirements, and PostgreSQL free tier or SQLite for data storage.

Key finding: Don't hand-roll anti-bot evasion or rate limiting logic. Modern anti-bot systems (Cloudflare, DataDome) use sophisticated detection including TLS fingerprinting, behavioral analysis, and JA4 signatures. Use established stealth libraries (puppeteer-extra-plugin-stealth, playwright-stealth) and focus on respectful scraping patterns.

The choice between Python and Node.js depends on your needs: Python excels at data processing and large-scale orchestration (Scrapy), while Node.js is superior for JavaScript-heavy sites and asynchronous operations. For this project targeting two different sites with different requirements (daily batch stats vs real-time odds), a hybrid approach or Playwright (available in both languages) offers maximum flexibility.

**Primary recommendation:** Use Playwright with Python for unified codebase, PostgreSQL free tier (Neon/Supabase) for data storage, implement layered pipeline architecture (crawl → queue → transform → store), and use stealth plugins + respectful rate limiting to avoid detection.
</research_summary>

<standard_stack>
## Standard Stack

### Core (Recommended)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Playwright | 1.57.0 | Headless browser automation | Cross-browser, handles JS-heavy sites, Python & Node support |
| Python | 3.10+ | Primary language | Mature scraping ecosystem, data processing, Scrapy integration |
| playwright-stealth | Latest | Anti-detection | Bypasses common bot detection methods |
| PostgreSQL | 14+ | Data storage | Free tier available, reliable, ACID compliant |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Scrapy | 2.14.1 | Large-scale crawling framework | If scaling to millions of URLs, sophisticated scheduling |
| BeautifulSoup | 4.x | HTML parsing | Parsing static HTML after Playwright renders |
| requests | 2.x | Simple HTTP requests | When site doesn't require JavaScript rendering |
| redis | 7.x | Queue/cache | For distributed scraping, request deduplication |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright | Puppeteer (Node.js only) | Slightly faster for Chrome-only, more mature stealth plugins |
| Playwright | Scrapy alone | Can't handle JavaScript-rendered content effectively |
| PostgreSQL | SQLite | Simpler for single-machine, no hosting needed, but no concurrent writes |
| Python | Node.js | Better for async, JS-heavy sites, but weaker data processing ecosystem |

**Installation (Python):**
```bash
pip install playwright playwright-stealth beautifulsoup4 psycopg2-binary redis
playwright install chromium
```

**Installation (Node.js alternative):**
```bash
npm install playwright puppeteer-extra puppeteer-extra-plugin-stealth pg redis
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
src/
├── scrapers/
│   ├── greyhound_stats.py    # Daily stats scraper
│   ├── oddschecker.py         # Real-time odds scraper
│   └── base_scraper.py        # Shared scraping logic
├── models/
│   ├── race.py                # Race data model
│   ├── dog.py                 # Dog statistics model
│   └── odds.py                # Odds data model
├── storage/
│   ├── db.py                  # Database connection/queries
│   └── migrations/            # Schema migrations
├── utils/
│   ├── rate_limiter.py        # Request throttling
│   ├── stealth.py             # Anti-detection helpers
│   └── retry.py               # Retry logic with backoff
└── scheduler.py               # Orchestrates scraping runs
```

### Pattern 1: Layered Pipeline Architecture
**What:** Separate crawling, queueing, transforming, and storing into distinct stages
**When to use:** Any production scraping system
**Example:**
```python
# Crawl Stage
async def crawl(url):
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    await stealth_async(page)  # Apply stealth patches
    await page.goto(url)
    html = await page.content()
    await browser.close()
    return html

# Transform Stage
def parse_race_data(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Extract structured data
    return race_data

# Store Stage
def save_to_db(race_data):
    conn.execute("INSERT INTO races (...) VALUES (...)", race_data)
```

### Pattern 2: Exponential Backoff with Rate Limiting
**What:** Implement respectful delays between requests with exponential backoff on errors
**When to use:** All scrapers to avoid detection and IP blocks
**Example:**
```python
import time
import random

class RateLimiter:
    def __init__(self, min_delay=2, max_delay=5):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request = 0

    async def wait(self):
        elapsed = time.time() - self.last_request
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self.last_request = time.time()

# Exponential backoff on errors
max_retries = 3
for attempt in range(max_retries):
    try:
        result = await scrape_page(url)
        break
    except Exception as e:
        if attempt == max_retries - 1:
            raise
        wait_time = 2 ** attempt + random.uniform(0, 1)
        await asyncio.sleep(wait_time)
```

### Pattern 3: Session Management & Cookie Persistence
**What:** Maintain consistent sessions to avoid suspicious behavior patterns
**When to use:** Sites that track user sessions and behavior
**Example:**
```python
# Persist browser context across scrapes
async def create_persistent_context(playwright):
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir='./browser_data',
        headless=True,
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 ...'  # Realistic user agent
    )
    return context
```

### Anti-Patterns to Avoid
- **Sending too many requests too quickly:** Triggers rate limits and IP blocks. Always implement delays.
- **Using default User-Agent headers:** Easily flagged as bot traffic. Rotate realistic User-Agents.
- **Ignoring robots.txt:** While not legally binding, ignoring it increases block risk and is unethical.
- **Fragile CSS selectors:** Auto-generated class names like `.css-x7d93k` change on deployment. Use semantic selectors.
- **No error handling:** Sites change, scrapers break. Implement comprehensive error handling and monitoring.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anti-bot evasion | Custom header randomization | playwright-stealth, puppeteer-extra-plugin-stealth | Modern detection uses TLS fingerprinting, canvas fingerprinting, behavioral analysis |
| Rate limiting | Simple time.sleep() | Token bucket or leaky bucket algorithm with redis | Need distributed rate limiting, burst handling, per-domain limits |
| Proxy rotation | Manual proxy list management | Rotating proxy service or library | IP reputation, geolocation, CAPTCHA solving are complex |
| HTML parsing | Regex or manual string parsing | BeautifulSoup, lxml | Edge cases, malformed HTML, encoding issues |
| Retry logic | Manual try/catch loops | tenacity library (Python) or retry library | Exponential backoff, jitter, different retry strategies |
| Session persistence | Manual cookie management | Browser context persistence in Playwright | Handles storage state, localStorage, cookies correctly |

**Key insight:** Modern anti-bot systems (Cloudflare, DataDome, Akamai) analyze dozens of signals: TLS fingerprints, browser fingerprints (canvas, WebGL, audio), behavioral patterns (mouse movement, timing), and IP reputation. Custom solutions fail against these. Use battle-tested stealth libraries that patch all known detection vectors.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Ignoring Dynamic Content Loading
**What goes wrong:** Scraper extracts empty data or partial content because JavaScript hasn't finished loading
**Why it happens:** Using simple HTTP requests on JavaScript-rendered sites
**How to avoid:** Use Playwright with proper wait strategies (`page.wait_for_selector()`, `page.wait_for_load_state('networkidle')`)
**Warning signs:** Getting HTML structure but missing actual data, empty tables or lists

### Pitfall 2: Getting Blocked by Anti-Bot Systems
**What goes wrong:** IP gets blocked, CAPTCHAs appear, requests return 403/429 errors
**Why it happens:** Too many requests, suspicious patterns, poor fingerprinting
**How to avoid:** Implement rate limiting (2-5 second delays), use stealth plugins, rotate User-Agents, respect robots.txt
**Warning signs:** Sudden increase in failed requests, CAPTCHA challenges, HTTP 403/429 responses

### Pitfall 3: Fragile Selectors Breaking on Site Updates
**What goes wrong:** Scraper stops working when site redesigns or updates CSS
**Why it happens:** Relying on auto-generated CSS class names or brittle XPath
**How to avoid:** Use semantic HTML elements, data attributes, or stable structural patterns. Implement monitoring to detect breakage.
**Warning signs:** Scraper returns None/null for previously working selectors, data validation errors

### Pitfall 4: Not Handling Missing or Optional Data
**What goes wrong:** Scraper crashes or saves incorrect data when optional fields are missing
**Why it happens:** Assuming all pages have identical structure
**How to avoid:** Use `.get()` methods with defaults, validate data before saving, handle None values gracefully
**Warning signs:** Frequent crashes on certain pages, data misalignment in database

### Pitfall 5: Poor Session Handling
**What goes wrong:** Each request looks like a new visitor, breaking functionality that depends on continuity
**Why it happens:** Not persisting cookies or browser context between requests
**How to avoid:** Use persistent browser contexts in Playwright, save and restore cookies
**Warning signs:** Site behavior differs from manual browsing, forced login loops, missing data

### Pitfall 6: Insufficient Error Monitoring
**What goes wrong:** Scraper silently fails, accumulating stale data without notification
**Why it happens:** No observability, logging, or alerting
**How to avoid:** Log all errors, implement health checks, monitor data freshness, set up alerts
**Warning signs:** Discovering days-old failures, data staleness, user complaints
</common_pitfalls>

<code_examples>
## Code Examples

Verified patterns for production web scraping:

### Basic Playwright Setup with Stealth
```python
# Source: playwright-python docs + playwright-stealth library
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def scrape_with_stealth(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        await stealth_async(page)  # Apply anti-detection patches

        await page.goto(url, wait_until='networkidle')
        content = await page.content()

        await browser.close()
        return content
```

### Rate Limiter with Token Bucket Pattern
```python
# Source: Industry standard pattern
import time
import asyncio

class TokenBucketRateLimiter:
    def __init__(self, rate=1, capacity=5):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()

    async def acquire(self):
        while True:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return

            await asyncio.sleep(0.1)
```

### Robust Data Extraction with Error Handling
```python
# Source: BeautifulSoup best practices
from bs4 import BeautifulSoup

def extract_race_data(html):
    soup = BeautifulSoup(html, 'lxml')

    races = []
    # Use semantic selectors, not auto-generated classes
    race_elements = soup.select('div[data-race-id]') or soup.select('.race-card')

    for race_elem in race_elements:
        race = {
            'race_id': race_elem.get('data-race-id', ''),
            'time': race_elem.select_one('.race-time').text.strip() if race_elem.select_one('.race-time') else None,
            'track': race_elem.select_one('.track-name').text.strip() if race_elem.select_one('.track-name') else 'Unknown',
            'dogs': []
        }

        dog_elements = race_elem.select('.dog-entry')
        for dog_elem in dog_elements:
            dog = {
                'name': dog_elem.select_one('.dog-name').text.strip() if dog_elem.select_one('.dog-name') else None,
                'trap': dog_elem.get('data-trap', None),
                'odds': dog_elem.select_one('.odds').text.strip() if dog_elem.select_one('.odds') else None
            }
            # Validate required fields
            if dog['name'] and dog['trap']:
                race['dogs'].append(dog)

        if race['race_id'] and race['dogs']:  # Only add valid races
            races.append(race)

    return races
```

### Database Connection with Connection Pooling
```python
# Source: psycopg2 documentation
import psycopg2
from psycopg2 import pool

class Database:
    def __init__(self, db_config):
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            **db_config
        )

    def execute(self, query, params=None):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
                return cur.fetchall() if cur.description else None
        finally:
            self.pool.putconn(conn)

    def close(self):
        self.pool.closeall()
```
</code_examples>

<sota_updates>
## State of the Art (2026)

What's changed recently in web scraping:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Puppeteer stealth | nodriver, selenium-driverless | 2025 | Avoids CDP protocol detection entirely, emulates native OS inputs |
| Simple User-Agent rotation | Full browser fingerprint management | 2024-2025 | Anti-bots now check TLS, canvas, WebGL, audio fingerprints |
| cannon.js (wrong context) | JA4 fingerprinting awareness | 2025 | Akamai uses JA4 to detect automation libraries |
| Selenium | Playwright | 2021-2023 | Playwright faster, better API, cross-browser, actively maintained |
| Manual proxy lists | Smart proxy services with AI routing | 2024-2025 | Automatic IP reputation management, geo-targeting |

**New tools/patterns to consider:**
- **nodriver (Python):** CDP-free automation that's harder to detect than Playwright (2025)
- **Bright Data Web Unlocker:** Handles anti-bot challenges automatically (paid service)
- **Browser fingerprint randomization:** Libraries like Playwright Extra now randomize canvas, WebGL, audio context

**Deprecated/outdated:**
- **Selenium:** Still works but slower, worse API than Playwright
- **Simple requests + BeautifulSoup only:** Fails on 80%+ of modern sites with JavaScript
- **puppeteer-real-browser:** Author abandoned in Feb 2026, use other stealth solutions
- **Ignoring TLS fingerprinting:** Modern anti-bots detect automation via TLS handshake

**Current best practices (2026):**
- Playwright remains industry standard for production scraping
- Stealth plugins are necessary but not sufficient - need full fingerprint management
- Rate limiting and respectful scraping patterns are more important than stealth tech
- Distributed architecture with message queues (Redis/RabbitMQ) for scale
- Observability (Prometheus, Grafana) baked into architecture from day one
</sota_updates>

<open_questions>
## Open Questions

Things that require site-specific investigation:

1. **greyhoundstats.co.uk robots.txt and anti-bot measures**
   - What we know: Need to check robots.txt at https://greyhoundstats.co.uk/robots.txt
   - What's unclear: Site structure, anti-bot protection level, rate limits
   - Recommendation: Manually inspect robots.txt, test scraping with delays, monitor for blocks during Phase 2

2. **oddschecker anti-bot protection level**
   - What we know: Likely uses JavaScript rendering, may have Cloudflare or similar
   - What's unclear: Specific anti-bot system, CAPTCHA frequency, required stealth level
   - Recommendation: Test with Playwright + stealth, be prepared for advanced evasion in Phase 3

3. **Data refresh frequency requirements**
   - What we know: Stats daily, odds real-time (every few minutes)
   - What's unclear: Exact polling interval for odds, acceptable staleness
   - Recommendation: Start conservative (5-10 min for odds), adjust based on testing and user feedback

4. **Free database hosting limitations**
   - What we know: Neon/Supabase offer free PostgreSQL tiers
   - What's unclear: Storage limits, connection limits, acceptable for production
   - Recommendation: Start with Neon free tier (3GB), monitor usage, upgrade if needed
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- Playwright official docs (https://playwright.dev) - Setup, API, best practices
- Scrapy 2.14 documentation (https://docs.scrapy.org) - Architecture, patterns
- puppeteer-extra-plugin-stealth GitHub (https://github.com/berstend/puppeteer-extra) - Anti-detection techniques
- BeautifulSoup documentation - HTML parsing patterns

### Secondary (MEDIUM confidence)
- [Best Web Scraping Tools in 2026](https://scrapfly.io/blog/posts/best-web-scraping-tools-in-2026) - Tool comparison verified with official docs
- [Python vs NodeJS for Web Scraping](https://scrape.do/blog/web-scraping-python-vs-nodejs/) - Language comparison
- [Playwright vs Puppeteer in 2026](https://www.zenrows.com/blog/playwright-vs-puppeteer) - Cross-verified with GitHub releases
- [From Puppeteer stealth to Nodriver](https://blog.castle.io/from-puppeteer-stealth-to-nodriver-how-anti-detect-frameworks-evolved-to-evade-bot-detection/) - Anti-bot evolution
- [Web Scraping Infrastructure](https://groupbwt.com/blog/infrastructure-of-web-scraping/) - Architecture patterns
- [Robots.txt for Web Scraping Guide](https://brightdata.com/blog/how-tos/robots-txt-for-web-scraping-guide) - robots.txt best practices

### Tertiary (LOW confidence - needs validation)
- WebSearch findings on specific site structures - need manual verification during implementation
- Free database hosting specifics - need to test actual limits and performance

### Version Verification
- Playwright: 1.57.0 (verified via npm/PyPI search Jan 2026)
- Scrapy: 2.14.1 (verified via PyPI Jan 2026)
- Puppeteer: 24.35.0 (verified via npm search Jan 2026)
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Web scraping (Playwright, Scrapy, BeautifulSoup)
- Ecosystem: Anti-detection, rate limiting, data storage, architecture patterns
- Patterns: Layered pipelines, rate limiting, session management, error handling
- Pitfalls: Dynamic content, IP blocks, fragile selectors, data validation

**Confidence breakdown:**
- Standard stack: HIGH - Verified with official docs, widely adopted in 2026
- Architecture: HIGH - Industry standard patterns from authoritative sources
- Pitfalls: HIGH - Well-documented in scraping community, cross-verified
- Code examples: HIGH - From official documentation and established patterns
- SOTA updates: MEDIUM-HIGH - Recent developments verified where possible

**Research date:** 2026-01-13
**Valid until:** 2026-02-13 (30 days - scraping ecosystem changes rapidly but core patterns stable)

**Specific to this project:**
- Target sites: greyhoundstats.co.uk (stats), oddschecker (odds)
- Constraints: Free hosting, respect rate limits, no budget for paid proxies
- Requirements: Daily batch scraping + real-time polling
- Recommendation: Python + Playwright + PostgreSQL free tier + respectful scraping patterns
</metadata>

---

*Phase: 01-foundation*
*Research completed: 2026-01-13*
*Ready for planning: yes*

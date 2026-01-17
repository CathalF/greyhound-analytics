"""
Full Sequential Scraper

Discovers upcoming races from oddschecker, scrapes odds, then fetches dog stats
from greyhoundstats for each dog - all in sequence, race by race.

Flow:
1. Discover races from oddschecker listings
2. For each race:
   a. Scrape race card and odds from oddschecker
   b. For each dog in the race:
      - Check if dog exists in database with recent stats
      - If not, scrape stats from greyhoundstats.co.uk
   c. Store race, link dogs, store odds
3. Move to next race

Usage:
    # Scrape all races in next 4 hours
    python -m src.full_scraper

    # Scrape races in next 6 hours
    python -m src.full_scraper --hours 6

    # Scrape specific number of races
    python -m src.full_scraper --limit 5

    # Force refresh dog stats even if recent
    python -m src.full_scraper --refresh-stats
"""

import asyncio
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from src.scrapers.oddschecker_scraper import OddscheckerScraper
from src.scrapers.greyhound_stats_scraper import GreyhoundStatsScraper
from src.storage.race_odds import (
    upsert_race, link_dog_to_race, upsert_odds,
    get_upcoming_races, update_race_status
)
from src.storage.dog_stats import upsert_dog_stats, get_dog_stats
from src.storage.dog_matcher import match_dog_to_stats
from src.utils.rate_limiter import TokenBucketRateLimiter
from src.utils.stealth import setup_stealth_page, get_browser_launch_args


# Configure logging
def setup_logging():
    """Configure structured logging with file rotation"""
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger('full_scraper')
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    logger.handlers = []

    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/full_scraper.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()


# Stats refresh threshold (hours)
STATS_REFRESH_THRESHOLD = 24


async def discover_races(hours_ahead: int = 4) -> List[str]:
    """
    Discover upcoming races from oddschecker listings page.

    Returns list of race URLs for the next N hours.
    """
    logger.info(f"Discovering races for next {hours_ahead} hours...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=get_browser_launch_args()
        )
        page = await browser.new_page()
        page = await setup_stealth_page(page)

        try:
            await page.goto("https://www.oddschecker.com/greyhounds", timeout=30000)
            await asyncio.sleep(3)

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            race_links = []
            seen = set()

            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if '/greyhounds/' in href and '/winner' in href and href.count('/') >= 3:
                    text = link.get_text(strip=True)
                    if 'closed' not in text.lower():
                        full_url = f"https://www.oddschecker.com{href}" if href.startswith('/') else href
                        if full_url not in seen:
                            seen.add(full_url)
                            race_links.append(full_url)

            logger.info(f"Found {len(race_links)} upcoming races")
            return race_links

        except Exception as e:
            logger.error(f"Failed to discover races: {e}")
            return []

        finally:
            await browser.close()


async def scrape_dog_stats(dog_name: str, rate_limiter: TokenBucketRateLimiter) -> Optional[Dict[str, Any]]:
    """
    Scrape stats for a single dog from greyhoundstats.co.uk.

    Args:
        dog_name: Name of the dog
        rate_limiter: Shared rate limiter

    Returns:
        Stats dict or None if scraping failed
    """
    # Build URL with encoded dog name
    encoded_name = quote(dog_name)
    url = f"https://greyhoundstats.co.uk/complete_runner_stats.php?dog={encoded_name}"

    try:
        scraper = GreyhoundStatsScraper(url, rate_limiter)
        stats = await scraper.run()

        if stats and stats.get('runs') is not None:
            return stats
        else:
            logger.debug(f"  No stats found for {dog_name}")
            return None

    except Exception as e:
        logger.warning(f"  Failed to scrape stats for {dog_name}: {e}")
        return None


def needs_stats_refresh(dog_name: str, force_refresh: bool = False) -> bool:
    """
    Check if a dog needs its stats refreshed.

    Args:
        dog_name: Dog name
        force_refresh: Force refresh regardless of age

    Returns:
        True if stats should be scraped
    """
    if force_refresh:
        return True

    dog = get_dog_stats(dog_name)

    if not dog:
        return True  # New dog, needs stats

    last_update = dog.get('last_stats_update')
    if not last_update:
        return True

    # Check if stats are older than threshold
    age = datetime.now() - last_update
    return age > timedelta(hours=STATS_REFRESH_THRESHOLD)


async def process_race(
    race_url: str,
    rate_limiter: TokenBucketRateLimiter,
    force_refresh_stats: bool = False
) -> Dict[str, Any]:
    """
    Process a single race: scrape odds, fetch dog stats, store everything.

    Args:
        race_url: URL to race card on oddschecker
        rate_limiter: Shared rate limiter
        force_refresh_stats: Force refresh dog stats even if recent

    Returns:
        Dict with processing stats
    """
    stats = {
        'race_id': None,
        'track': None,
        'time': None,
        'dogs_found': 0,
        'dogs_matched': 0,
        'dogs_stats_scraped': 0,
        'odds_stored': 0,
        'success': False
    }

    # Step 1: Scrape race and odds from oddschecker
    logger.info(f"  Scraping odds from oddschecker...")
    try:
        scraper = OddscheckerScraper(race_url, rate_limiter)
        race_data = await scraper.run()
    except Exception as e:
        logger.error(f"  Failed to scrape race: {e}")
        return stats

    if not race_data:
        logger.error(f"  No race data returned")
        return stats

    stats['race_id'] = race_data['race_id']
    stats['track'] = race_data['track']
    stats['time'] = race_data['time']
    stats['dogs_found'] = len(race_data.get('dogs', []))

    logger.info(f"  Found {stats['dogs_found']} dogs at {stats['track']} {stats['time']}")

    # Step 2: Store race
    race_to_store = {
        'race_id': race_data['race_id'],
        'track': race_data['track'],
        'time': race_data['time'],
        'distance': race_data.get('distance')
    }
    upsert_race(race_to_store)

    # Step 3: For each dog, check/fetch stats
    matched_dogs = []

    for dog in race_data.get('dogs', []):
        dog_name = dog['name']
        trap = dog.get('trap')

        logger.info(f"    Processing: {dog_name} (Trap {trap})")

        # Check if dog needs stats
        if needs_stats_refresh(dog_name, force_refresh_stats):
            logger.info(f"      Fetching stats from greyhoundstats...")
            dog_stats = await scrape_dog_stats(dog_name, rate_limiter)

            if dog_stats:
                # Store stats in database
                success = upsert_dog_stats(dog_name, {
                    'runs': dog_stats.get('runs'),
                    'wins': dog_stats.get('wins'),
                    'win_rate': dog_stats.get('win_rate'),
                    'recent_form': dog_stats.get('recent_form', []),
                    'track_stats': dog_stats.get('track_stats', {}),
                    'distance_stats': dog_stats.get('distance_stats', {}),
                    'grade_stats': dog_stats.get('grade_stats', {}),
                    'latest_rating': dog_stats.get('latest_rating')
                })

                if success:
                    stats['dogs_stats_scraped'] += 1
                    logger.info(f"      Stats saved: {dog_stats.get('runs')} runs, {dog_stats.get('win_rate')}% win rate")
        else:
            logger.info(f"      Stats already up to date")

        # Try to match dog to stats database
        dog_id, confidence = match_dog_to_stats(dog_name)

        if dog_id and confidence > 0:
            stats['dogs_matched'] += 1
            matched_dogs.append({
                'dog_id': dog_id,
                'name': dog_name,
                'trap': trap
            })

            # Link dog to race
            if trap and 1 <= trap <= 8:
                link_dog_to_race(dog_id, race_data['race_id'], trap)

    # Step 4: Store odds for matched dogs
    if matched_dogs:
        matched_dog_ids = {dog['name']: dog['dog_id'] for dog in matched_dogs}

        odds_to_store = []
        for odd in race_data.get('odds', []):
            if odd['dog_name'] in matched_dog_ids:
                odds_to_store.append({
                    'race_id': race_data['race_id'],
                    'dog_id': matched_dog_ids[odd['dog_name']],
                    'bookmaker': odd['bookmaker'],
                    'decimal': odd['decimal'],
                    'fractional': odd['fractional']
                })

        if odds_to_store:
            stats['odds_stored'] = upsert_odds(odds_to_store)

    # Update race status
    try:
        hour, minute = map(int, race_data['time'].split(':'))
        today = datetime.now().date()
        race_datetime = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
        time_until = (race_datetime - datetime.now()).total_seconds() / 60

        if time_until < 0:
            update_race_status(race_data['race_id'], 'complete')
        elif time_until < 30:
            update_race_status(race_data['race_id'], 'imminent')
        else:
            update_race_status(race_data['race_id'], 'upcoming')
    except:
        update_race_status(race_data['race_id'], 'upcoming')

    stats['success'] = True
    return stats


async def run_full_scrape(
    hours_ahead: int = 4,
    limit: Optional[int] = None,
    force_refresh_stats: bool = False
):
    """
    Run full sequential scrape of races and dog stats.

    Args:
        hours_ahead: Hours to look ahead for races
        limit: Maximum number of races to process (None = all)
        force_refresh_stats: Force refresh dog stats even if recent
    """
    logger.info("=" * 80)
    logger.info("FULL SEQUENTIAL SCRAPER")
    logger.info("=" * 80)
    logger.info(f"Hours ahead: {hours_ahead}")
    logger.info(f"Race limit: {limit or 'No limit'}")
    logger.info(f"Force refresh stats: {force_refresh_stats}")
    logger.info("=" * 80)

    # Discover races
    race_urls = await discover_races(hours_ahead)

    if not race_urls:
        logger.warning("No races found")
        return

    # Apply limit if specified
    if limit:
        race_urls = race_urls[:limit]
        logger.info(f"Limited to {limit} races")

    # Create shared rate limiter (slower to be safe with two sites)
    rate_limiter = TokenBucketRateLimiter(rate=0.33)  # ~3 second delays

    # Process each race sequentially
    totals = {
        'races_processed': 0,
        'races_failed': 0,
        'total_dogs': 0,
        'total_matched': 0,
        'total_stats_scraped': 0,
        'total_odds': 0
    }

    for i, race_url in enumerate(race_urls, 1):
        logger.info("")
        logger.info(f"[{i}/{len(race_urls)}] {race_url}")
        logger.info("-" * 60)

        result = await process_race(race_url, rate_limiter, force_refresh_stats)

        if result['success']:
            totals['races_processed'] += 1
            totals['total_dogs'] += result['dogs_found']
            totals['total_matched'] += result['dogs_matched']
            totals['total_stats_scraped'] += result['dogs_stats_scraped']
            totals['total_odds'] += result['odds_stored']

            logger.info(f"  DONE: {result['dogs_matched']}/{result['dogs_found']} dogs matched, "
                       f"{result['dogs_stats_scraped']} stats scraped, "
                       f"{result['odds_stored']} odds stored")
        else:
            totals['races_failed'] += 1
            logger.error(f"  FAILED")

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SCRAPE COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Races processed: {totals['races_processed']}/{len(race_urls)}")
    logger.info(f"Races failed: {totals['races_failed']}")
    logger.info(f"Total dogs found: {totals['total_dogs']}")
    logger.info(f"Dogs matched to DB: {totals['total_matched']}")
    logger.info(f"Dog stats scraped: {totals['total_stats_scraped']}")
    logger.info(f"Odds records stored: {totals['total_odds']}")
    logger.info("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Full sequential scraper for races and dog stats'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=4,
        help='Hours ahead to discover races (default: 4)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of races to process'
    )
    parser.add_argument(
        '--refresh-stats',
        action='store_true',
        help='Force refresh dog stats even if recently updated'
    )

    args = parser.parse_args()

    asyncio.run(run_full_scrape(
        hours_ahead=args.hours,
        limit=args.limit,
        force_refresh_stats=args.refresh_stats
    ))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\nScrape stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()

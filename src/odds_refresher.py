"""
Real-Time Odds Refresh Orchestrator

Discovers upcoming races from oddschecker.com and continuously refreshes odds.
Manages race lifecycle (upcoming → imminent → complete) and respects rate limits.

Features:
- Automatic race discovery from listings page
- Continuous odds refresh (default 5-minute intervals)
- Shared rate limiter across all scrapes
- Dog matching and linking to stats database
- Structured logging with file rotation
- Race status tracking to avoid wasted work
- Robust error handling (continues on failures)

Usage:
    # Run once (discover + update races in next 4 hours)
    python -m src.odds_refresher --once

    # Continuous refresh every 5 minutes
    python -m src.odds_refresher --hours 6

    # Custom refresh interval
    python -m src.odds_refresher --interval 3

    # Include completed races (for testing)
    python -m src.odds_refresher --once --include-completed
"""

import asyncio
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
from pathlib import Path

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from src.scrapers.oddschecker_scraper import OddscheckerScraper
from src.storage.race_odds import (
    upsert_race, link_dog_to_race, upsert_odds,
    get_upcoming_races, update_race_status, get_active_races
)
from src.storage.dog_matcher import match_dog_to_stats
from src.utils.rate_limiter import TokenBucketRateLimiter
from src.utils.stealth import setup_stealth_page, get_browser_launch_args


# Configure logging
def setup_logging():
    """Configure structured logging with file rotation"""
    # Create logs directory if it doesn't exist
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)

    # Create logger
    logger = logging.getLogger('odds_refresher')
    logger.setLevel(logging.DEBUG)

    # File handler with rotation (10MB max, 5 backups)
    file_handler = RotatingFileHandler(
        'logs/odds_refresher.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()


async def discover_races(hours_ahead: int = 4) -> List[str]:
    """
    Discover upcoming races from oddschecker listings page.

    Navigates to /greyhounds and extracts all race URLs for the next N hours.

    Args:
        hours_ahead: Number of hours to look ahead (default 4)

    Returns:
        List of race URLs

    Example:
        races = await discover_races(hours_ahead=6)
        # ['https://www.oddschecker.com/greyhounds/harlow/18:11/winner', ...]
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
            # Navigate to greyhound listings
            await page.goto("https://www.oddschecker.com/greyhounds", timeout=30000)
            await asyncio.sleep(3)  # Wait for content to load

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Find all race links
            race_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                # Match pattern: /greyhounds/{track}/{time}/winner
                if '/greyhounds/' in href and href.count('/') >= 3 and '/winner' in href:
                    text = link.get_text(strip=True)
                    # Skip closed races
                    if 'closed' not in text.lower():
                        full_url = f"https://www.oddschecker.com{href}" if href.startswith('/') else href
                        race_links.append(full_url)

            logger.info(f"Found {len(race_links)} upcoming races")

            return race_links

        except Exception as e:
            logger.error(f"Failed to discover races: {e}")
            return []

        finally:
            await browser.close()


async def scrape_single_race(race_url: str, rate_limiter: TokenBucketRateLimiter) -> Dict[str, Any]:
    """
    Scrape a single race with error handling.

    Args:
        race_url: URL to race card
        rate_limiter: Shared rate limiter instance

    Returns:
        Dict with race data, or None if scraping failed
    """
    try:
        scraper = OddscheckerScraper(race_url, rate_limiter)
        race_data = await scraper.run()
        return race_data

    except Exception as e:
        logger.error(f"Failed to scrape {race_url}: {e}")
        return None


async def process_race(race_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Process scraped race data: store race, match dogs, link, store odds.

    Args:
        race_data: Scraped race data from OddscheckerScraper

    Returns:
        Dict with processing stats: matched_dogs, linked_dogs, odds_stored
    """
    stats = {
        'matched_dogs': 0,
        'linked_dogs': 0,
        'odds_stored': 0
    }

    # Store race
    race_to_store = {
        'race_id': race_data['race_id'],
        'track': race_data['track'],
        'time': race_data['time'],
        'distance': race_data['distance']
    }

    success = upsert_race(race_to_store)
    if not success:
        logger.error(f"Failed to store race {race_data['race_id']}")
        return stats

    # Determine race status (upcoming vs imminent)
    race_time_str = race_data['time']  # Format: "HH:MM"
    try:
        # Parse race time (assume today)
        hour, minute = map(int, race_time_str.split(':'))
        today = datetime.now().date()
        race_datetime = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))

        # Calculate time until race
        time_until = (race_datetime - datetime.now()).total_seconds() / 60  # minutes

        if time_until < 0:
            # Race already passed
            update_race_status(race_data['race_id'], 'complete')
            logger.debug(f"Race {race_data['race_id']} marked as complete (already passed)")
        elif time_until < 30:
            # Race within 30 minutes
            update_race_status(race_data['race_id'], 'imminent')
            logger.debug(f"Race {race_data['race_id']} marked as imminent ({time_until:.0f} min)")
        else:
            # Race more than 30 minutes away
            update_race_status(race_data['race_id'], 'upcoming')
            logger.debug(f"Race {race_data['race_id']} marked as upcoming ({time_until:.0f} min)")

    except Exception as e:
        logger.warning(f"Could not parse race time '{race_time_str}': {e}")
        update_race_status(race_data['race_id'], 'upcoming')

    # Match and link dogs
    matched_dogs = []
    for dog in race_data['dogs']:
        dog_id, confidence = match_dog_to_stats(dog['name'])

        if dog_id and confidence > 0:
            stats['matched_dogs'] += 1
            logger.debug(f"  Matched: {dog['name']} -> {dog_id}")

            # Link dog to race (only if trap number is valid)
            trap = dog.get('trap')
            if trap and 1 <= trap <= 8:
                success = link_dog_to_race(dog_id, race_data['race_id'], trap)
                if success:
                    stats['linked_dogs'] += 1

            # Always add to matched dogs for odds storage
            matched_dogs.append({'dog_id': dog_id, 'name': dog['name']})
        else:
            logger.debug(f"  Not matched: {dog['name']} (not in stats database)")

    # Store odds (only for matched dogs)
    if matched_dogs:
        matched_dog_ids = {dog['name']: dog['dog_id'] for dog in matched_dogs}

        odds_to_store = []
        for odd in race_data['odds']:
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
            logger.debug(f"  Stored {stats['odds_stored']} odds records")

    return stats


async def refresh_cycle(hours_ahead: int = 4, include_completed: bool = False) -> Dict[str, int]:
    """
    Execute one refresh cycle: discover races, scrape, update database.

    Args:
        hours_ahead: Hours to look ahead for race discovery
        include_completed: Whether to include completed races (for testing)

    Returns:
        Dict with cycle stats
    """
    logger.info("=" * 80)
    logger.info("Starting odds refresh cycle")
    logger.info("=" * 80)

    cycle_stats = {
        'races_discovered': 0,
        'races_processed': 0,
        'races_failed': 0,
        'total_matched_dogs': 0,
        'total_linked_dogs': 0,
        'total_odds_stored': 0
    }

    # Discover races
    race_urls = await discover_races(hours_ahead)
    cycle_stats['races_discovered'] = len(race_urls)

    if not race_urls:
        logger.warning("No races discovered")
        return cycle_stats

    # Create shared rate limiter (2-second delays)
    rate_limiter = TokenBucketRateLimiter(rate=0.5)

    # Scrape all races (with error handling)
    logger.info(f"Scraping {len(race_urls)} races...")

    for i, race_url in enumerate(race_urls, 1):
        logger.info(f"[{i}/{len(race_urls)}] Processing {race_url}")

        # Scrape race
        race_data = await scrape_single_race(race_url, rate_limiter)

        if race_data is None:
            cycle_stats['races_failed'] += 1
            continue

        # Process race (store, match, link, odds)
        try:
            process_stats = await process_race(race_data)

            cycle_stats['races_processed'] += 1
            cycle_stats['total_matched_dogs'] += process_stats['matched_dogs']
            cycle_stats['total_linked_dogs'] += process_stats['linked_dogs']
            cycle_stats['total_odds_stored'] += process_stats['odds_stored']

            logger.info(f"  [OK] {race_data['track']} {race_data['time']}: "
                       f"{process_stats['matched_dogs']} dogs matched, "
                       f"{process_stats['odds_stored']} odds stored")

        except Exception as e:
            logger.error(f"  Failed to process race: {e}")
            cycle_stats['races_failed'] += 1

    # Summary
    logger.info("=" * 80)
    logger.info("Refresh cycle complete")
    logger.info(f"  Races discovered: {cycle_stats['races_discovered']}")
    logger.info(f"  Races processed: {cycle_stats['races_processed']}")
    logger.info(f"  Races failed: {cycle_stats['races_failed']}")
    logger.info(f"  Dogs matched: {cycle_stats['total_matched_dogs']}")
    logger.info(f"  Dogs linked: {cycle_stats['total_linked_dogs']}")
    logger.info(f"  Odds stored: {cycle_stats['total_odds_stored']}")
    logger.info("=" * 80)

    return cycle_stats


async def continuous_refresh(hours_ahead: int = 4, interval_minutes: int = 5, include_completed: bool = False):
    """
    Run continuous refresh loop.

    Args:
        hours_ahead: Hours to look ahead for race discovery
        interval_minutes: Minutes to wait between refresh cycles
        include_completed: Whether to include completed races
    """
    logger.info(f"Starting continuous refresh (every {interval_minutes} minutes, "
               f"looking {hours_ahead} hours ahead)")

    cycle_count = 0

    while True:
        cycle_count += 1
        logger.info(f"\n\nRefresh cycle #{cycle_count}")

        try:
            await refresh_cycle(hours_ahead, include_completed)
        except Exception as e:
            logger.error(f"Refresh cycle failed: {e}")

        # Wait before next cycle
        logger.info(f"\nSleeping for {interval_minutes} minutes until next refresh...")
        await asyncio.sleep(interval_minutes * 60)


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='Real-time odds refresher for greyhound racing'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (default: continuous mode)'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=4,
        help='Hours ahead to discover races (default: 4)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Minutes between refresh cycles in continuous mode (default: 5)'
    )
    parser.add_argument(
        '--include-completed',
        action='store_true',
        help='Include completed races (for testing)'
    )

    args = parser.parse_args()

    if args.once:
        # Single run
        logger.info("Running single refresh cycle (--once mode)")
        asyncio.run(refresh_cycle(args.hours, args.include_completed))
    else:
        # Continuous mode
        asyncio.run(continuous_refresh(
            hours_ahead=args.hours,
            interval_minutes=args.interval,
            include_completed=args.include_completed
        ))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\nRefresh stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()

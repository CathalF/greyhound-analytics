"""
Results Collector Script

Periodically collects race results from oddschecker and updates betting history.
Intended to run every 30 minutes via cron/scheduler.

Usage:
    python src/results_collector.py           # Collect all pending results
    python src/results_collector.py --stats   # Show betting statistics only
    python src/results_collector.py --force   # Re-scrape even if results exist
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add project root to path for imports when running as script
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.scrapers.results_scraper import scrape_results_page, match_result_to_race
from src.storage.race_results import insert_race_results, get_race_results, get_betting_stats
from src.storage.race_odds import get_race_with_dogs, mark_race_complete
from src.services.value_finder import update_value_bet_outcomes
from src.storage.db import get_db
from src.utils.rate_limiter import TokenBucketRateLimiter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_races_needing_results() -> List[Dict[str, Any]]:
    """
    Get races that have passed but don't have results yet.

    Returns:
        List of race dictionaries that need results collection
    """
    db = get_db()

    try:
        now = datetime.now()
        # Look back up to 6 hours for missed results
        cutoff = now - timedelta(hours=6)

        query = """
            SELECT r.race_id, r.track_name, r.race_time, r.status
            FROM races r
            LEFT JOIN race_results rr ON r.race_id = rr.race_id
            WHERE r.race_time BETWEEN %s AND %s
            AND r.status != 'complete'
            AND rr.race_id IS NULL
            ORDER BY r.race_time DESC
        """

        results = db.execute_query(query, (cutoff, now), fetch=True)
        return [dict(row) for row in results] if results else []

    except Exception as e:
        logger.error(f"Error getting races needing results: {e}")
        return []


def get_all_pending_races() -> List[Dict[str, Any]]:
    """
    Get all races with pending status that have passed.

    For --force mode, includes races that may already have results.

    Returns:
        List of race dictionaries
    """
    db = get_db()

    try:
        now = datetime.now()
        cutoff = now - timedelta(hours=6)

        query = """
            SELECT race_id, track_name, race_time, status
            FROM races
            WHERE race_time BETWEEN %s AND %s
            ORDER BY race_time DESC
        """

        results = db.execute_query(query, (cutoff, now), fetch=True)
        return [dict(row) for row in results] if results else []

    except Exception as e:
        logger.error(f"Error getting pending races: {e}")
        return []


async def collect_results(force: bool = False) -> Dict[str, Any]:
    """
    Scrape today's results from oddschecker and update database.

    Args:
        force: If True, re-scrape even if results already exist

    Returns:
        Dict with collection statistics
    """
    stats = {
        'races_checked': 0,
        'races_updated': 0,
        'results_inserted': 0,
        'bets_updated': 0,
        'errors': []
    }

    # Get races that need results
    if force:
        pending_races = get_all_pending_races()
    else:
        pending_races = get_races_needing_results()

    if not pending_races:
        logger.info("No races need results collection")
        return stats

    stats['races_checked'] = len(pending_races)
    logger.info(f"Found {len(pending_races)} races that may need results")

    # Create rate limiter and scrape results page
    rate_limiter = TokenBucketRateLimiter(rate=0.5)  # 2-second delays

    try:
        scraped_results = await scrape_results_page(rate_limiter)
        logger.info(f"Scraped {len(scraped_results)} results from oddschecker")
    except Exception as e:
        logger.error(f"Error scraping results page: {e}")
        stats['errors'].append(f"Scrape error: {e}")
        return stats

    # Build lookup for scraped results by track+time
    results_lookup = {}
    for result in scraped_results:
        track = (result.get('track') or '').lower().replace(' ', '').replace('-', '')
        time = result.get('time')
        if track and time:
            key = f"{track}_{time}"
            results_lookup[key] = result

    # Process each race
    for race in pending_races:
        race_id = race['race_id']
        track_name = race['track_name']
        race_time = race['race_time']

        # Format time for lookup
        if isinstance(race_time, datetime):
            time_str = race_time.strftime('%H:%M')
        else:
            time_str = str(race_time)

        # Normalize track name
        track_normalized = track_name.lower().replace(' ', '').replace('-', '')
        lookup_key = f"{track_normalized}_{time_str}"

        # Check if we have results for this race
        result = results_lookup.get(lookup_key)
        if not result:
            logger.debug(f"No results found for {track_name} at {time_str}")
            continue

        # Check if results already exist (unless force mode)
        if not force:
            existing = get_race_results(race_id)
            if existing:
                logger.debug(f"Results already exist for {race_id}, skipping")
                continue

        # Match scraped dogs to database dogs
        matched_results = match_result_to_race(result, race_id)

        if not matched_results:
            logger.warning(f"Could not match any dogs for {race_id}")
            stats['errors'].append(f"No dog matches for {race_id}")
            continue

        # Insert results
        try:
            inserted = insert_race_results(race_id, matched_results)
            stats['results_inserted'] += inserted
            logger.info(f"Inserted {inserted} results for {race_id}")

            # Mark race as complete
            mark_race_complete(race_id)
            stats['races_updated'] += 1

        except Exception as e:
            logger.error(f"Error inserting results for {race_id}: {e}")
            stats['errors'].append(f"Insert error for {race_id}: {e}")

    # Update bet outcomes
    try:
        bets_updated = update_value_bet_outcomes()
        stats['bets_updated'] = bets_updated
        if bets_updated > 0:
            logger.info(f"Updated {bets_updated} bet outcomes")
    except Exception as e:
        logger.error(f"Error updating bet outcomes: {e}")
        stats['errors'].append(f"Bet update error: {e}")

    return stats


def print_summary(collection_stats: Dict[str, Any] = None):
    """
    Print today's results and betting performance.

    Args:
        collection_stats: Optional stats from collect_results()
    """
    print("\n" + "=" * 60)
    print("GREYHOUND ANALYTICS - RESULTS SUMMARY")
    print("=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    # Collection stats (if provided)
    if collection_stats:
        print("\nCOLLECTION RESULTS:")
        print(f"  Races checked:    {collection_stats.get('races_checked', 0)}")
        print(f"  Races updated:    {collection_stats.get('races_updated', 0)}")
        print(f"  Results inserted: {collection_stats.get('results_inserted', 0)}")
        print(f"  Bets updated:     {collection_stats.get('bets_updated', 0)}")

        errors = collection_stats.get('errors', [])
        if errors:
            print(f"  Errors:           {len(errors)}")
            for err in errors[:5]:  # Show first 5 errors
                print(f"    - {err}")

    # Betting statistics
    print("\nBETTING PERFORMANCE:")
    betting_stats = get_betting_stats()

    total_bets = betting_stats.get('total_bets', 0)
    pending = betting_stats.get('pending', 0)
    wins = betting_stats.get('wins', 0)
    losses = betting_stats.get('losses', 0)
    win_rate = betting_stats.get('win_rate', 0.0)
    total_profit = betting_stats.get('total_profit', 0.0)
    roi = betting_stats.get('roi', 0.0)

    print(f"  Total bets:       {total_bets}")
    print(f"  Pending:          {pending}")
    print(f"  Wins:             {wins}")
    print(f"  Losses:           {losses}")

    if wins + losses > 0:
        print(f"  Win rate:         {win_rate:.1f}%")
        print(f"  Total profit:     {total_profit:+.2f} units")
        print(f"  ROI:              {roi:+.1f}%")
    else:
        print("  (No resolved bets yet)")

    # Pending races
    print("\nPENDING RACES:")
    pending_races = get_races_needing_results()
    if pending_races:
        for race in pending_races[:10]:  # Show first 10
            race_time = race['race_time']
            if isinstance(race_time, datetime):
                time_str = race_time.strftime('%H:%M')
            else:
                time_str = str(race_time)
            print(f"  - {race['track_name']} at {time_str}")
        if len(pending_races) > 10:
            print(f"  ... and {len(pending_races) - 10} more")
    else:
        print("  No races pending results")

    print("\n" + "=" * 60)


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Collect race results and update betting history'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show betting statistics only (no scraping)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-scrape even if results already exist'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.stats:
        # Just show stats, no scraping
        print_summary()
    else:
        # Collect results and show summary
        logger.info("Starting results collection...")
        stats = asyncio.run(collect_results(force=args.force))
        print_summary(stats)
        logger.info("Results collection complete")


if __name__ == '__main__':
    main()

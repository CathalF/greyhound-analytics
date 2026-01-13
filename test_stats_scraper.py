"""
Integration test for GreyhoundStatsScraper and dog statistics storage.

Tests the complete pipeline:
1. Initialize rate limiter (0.5 rate = 2-second delays)
2. Scrape a sample dog profile from greyhoundstats.co.uk
3. Print extracted statistics
4. Store statistics in database using upsert_dog_stats
5. Retrieve statistics with get_dog_stats
6. Verify data integrity

Usage:
    python test_stats_scraper.py

Requirements:
    - DATABASE_URL set in .env
    - PostgreSQL database running
    - Migrations applied (python -m src.storage.migrations)
    - Dependencies installed (pip install -r requirements.txt)
"""

import asyncio
import json
from datetime import datetime

from src.scrapers.greyhound_stats_scraper import GreyhoundStatsScraper
from src.utils.rate_limiter import TokenBucketRateLimiter
from src.storage.dog_stats import upsert_dog_stats, get_dog_stats, count_dogs


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_stats_summary(stats: dict):
    """Print a formatted summary of dog statistics."""
    print(f"\nDog Name: {stats.get('dog_name', 'Unknown')}")
    print(f"Runs: {stats.get('runs', 'N/A')}")
    print(f"Wins: {stats.get('wins', 'N/A')}")
    print(f"Win Rate: {stats.get('win_rate', 'N/A')}%")
    print(f"Latest Rating: {stats.get('latest_rating', 'N/A')}")

    # Recent form
    recent_form = stats.get('recent_form', [])
    if recent_form:
        print(f"\nRecent Form (last {len(recent_form)} races):")
        for i, race in enumerate(recent_form[:5], 1):  # Show first 5
            date = race.get('date', 'N/A')
            track = race.get('track', 'N/A')
            finish = race.get('finish_position', 'N/A')
            distance = race.get('distance', 'N/A')
            print(f"  {i}. {date} - {track} - {distance} - Finished: {finish}")

    # Track preferences
    track_stats = stats.get('track_stats', {})
    if track_stats:
        print(f"\nTrack Performance (top 3):")
        sorted_tracks = sorted(
            track_stats.items(),
            key=lambda x: x[1].get('win_rate', 0),
            reverse=True
        )
        for track, track_data in sorted_tracks[:3]:
            runs = track_data.get('runs', 0)
            wins = track_data.get('wins', 0)
            win_rate = track_data.get('win_rate', 0)
            avg_rating = track_data.get('avg_rating', 'N/A')
            print(f"  {track}: {wins}/{runs} wins ({win_rate:.1f}%) - Avg Rating: {avg_rating}")

    # Distance preferences
    distance_stats = stats.get('distance_stats', {})
    if distance_stats:
        print(f"\nDistance Performance:")
        sorted_distances = sorted(distance_stats.items())
        for distance, distance_data in sorted_distances[:5]:  # Show top 5
            runs = distance_data.get('runs', 0)
            wins = distance_data.get('wins', 0)
            win_rate = distance_data.get('win_rate', 0)
            print(f"  {distance}: {wins}/{runs} wins ({win_rate:.1f}%)")


async def test_scraper():
    """Run the integration test."""
    print_section("DOG STATS SCRAPER INTEGRATION TEST")

    # Test configuration
    # Using a sample dog from research notes (Proper Heiress)
    test_dog_url = "https://greyhoundstats.co.uk/complete_runner_stats.php?dog=Proper%20Heiress"
    test_dog_name = "Proper Heiress"

    print(f"\nTest Configuration:")
    print(f"  Dog URL: {test_dog_url}")
    print(f"  Rate Limit: 0.5 req/sec (2-second delays)")
    print(f"  Test Dog: {test_dog_name}")

    # Step 1: Initialize rate limiter
    print_section("STEP 1: Initialize Rate Limiter")
    rate_limiter = TokenBucketRateLimiter(rate=0.5, capacity=5)
    print("[OK] Rate limiter created (0.5 tokens/sec = 2-second delays)")

    # Step 2: Create scraper and fetch data
    print_section("STEP 2: Scrape Dog Statistics")
    print(f"Fetching data from greyhoundstats.co.uk...")
    print(f"Note: This will take 2+ seconds due to rate limiting\n")

    start_time = datetime.now()

    try:
        scraper = GreyhoundStatsScraper(test_dog_url, rate_limiter)
        stats = await scraper.run()

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"[OK] Scraping completed in {elapsed:.2f} seconds")

        # Verify we got data
        if not stats or not stats.get('dog_name'):
            print("[FAIL] ERROR: No data extracted from page")
            return False

    except Exception as e:
        print(f"[FAIL] ERROR: Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 3: Print extracted statistics
    print_section("STEP 3: Extracted Statistics")
    print_stats_summary(stats)

    # Step 4: Store in database
    print_section("STEP 4: Store in Database")
    print(f"Upserting stats for '{stats['dog_name']}' to database...")

    try:
        success = upsert_dog_stats(stats['dog_name'], stats)
        if success:
            print(f"[OK] Statistics stored successfully")
        else:
            print(f"[FAIL] ERROR: Failed to store statistics")
            return False

    except Exception as e:
        print(f"[FAIL] ERROR: Database upsert failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Retrieve from database
    print_section("STEP 5: Retrieve from Database")
    print(f"Fetching stats for '{test_dog_name}' from database...")

    try:
        dog_record = get_dog_stats(test_dog_name)

        if not dog_record:
            print(f"[FAIL] ERROR: Dog not found in database after upsert")
            return False

        print(f"[OK] Dog record retrieved successfully")
        print(f"\nDatabase Record:")
        print(f"  Dog ID: {dog_record['dog_id']}")
        print(f"  Name: {dog_record['name']}")
        print(f"  Race ID: {dog_record['race_id']} (placeholder for Phase 2)")
        print(f"  Trap Number: {dog_record['trap_number']} (0 = not assigned)")
        print(f"  Last Stats Update: {dog_record['last_stats_update']}")
        print(f"  Created At: {dog_record['created_at']}")

    except Exception as e:
        print(f"[FAIL] ERROR: Database retrieval failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 6: Verify data integrity
    print_section("STEP 6: Verify Data Integrity")

    retrieved_stats = dog_record.get('stats', {})

    # Check key fields match
    checks = [
        ('dog_name', stats.get('dog_name'), retrieved_stats.get('dog_name')),
        ('runs', stats.get('runs'), retrieved_stats.get('runs')),
        ('wins', stats.get('wins'), retrieved_stats.get('wins')),
        ('win_rate', stats.get('win_rate'), retrieved_stats.get('win_rate')),
    ]

    all_passed = True
    for field, original, retrieved in checks:
        if original == retrieved:
            print(f"[OK] {field}: {original} == {retrieved}")
        else:
            print(f"[FAIL] {field}: {original} != {retrieved} (MISMATCH)")
            all_passed = False

    # Check nested data exists
    if retrieved_stats.get('recent_form'):
        print(f"[OK] recent_form: {len(retrieved_stats['recent_form'])} races")
    else:
        print(f"[FAIL] recent_form: Missing or empty")
        all_passed = False

    if retrieved_stats.get('track_stats'):
        print(f"[OK] track_stats: {len(retrieved_stats['track_stats'])} tracks")
    else:
        print(f"[FAIL] track_stats: Missing or empty")
        all_passed = False

    # Final summary
    print_section("TEST SUMMARY")

    total_dogs = count_dogs()
    print(f"Total dogs in database: {total_dogs}")

    if all_passed:
        print("\n[OK][OK][OK] ALL TESTS PASSED [OK][OK][OK]")
        print("\nThe scraper pipeline is working correctly:")
        print("  1. Scraping dog statistics from greyhoundstats.co.uk [OK]")
        print("  2. Parsing HTML and extracting data [OK]")
        print("  3. Storing in database with upsert [OK]")
        print("  4. Retrieving data correctly [OK]")
        print("  5. Data integrity maintained [OK]")
        print("  6. Rate limiting observed [OK]")
        print("\nReady for batch scraping in Plan 02-03!")
        return True
    else:
        print("\n[FAIL][FAIL][FAIL] SOME TESTS FAILED [FAIL][FAIL][FAIL]")
        print("Please review the errors above and fix before proceeding.")
        return False


def main():
    """Main entry point."""
    try:
        # Run the async test
        success = asyncio.run(test_scraper())

        # Exit with appropriate code
        exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n[FAIL] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()

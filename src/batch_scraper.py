"""
Batch Scraping Orchestrator for Dog Statistics

Orchestrates multi-dog scraping from greyhoundstats.co.uk with:
- Async processing of multiple dogs
- Shared rate limiting (respects 2-sec global rate limit)
- Graceful error handling (continues on failures)
- Structured logging with file rotation
- Progress tracking and resume capability
- Command-line flags: --limit N, --force

Usage:
    python -m src.batch_scraper              # Run full batch
    python -m src.batch_scraper --limit 10   # Test with first 10 dogs
    python -m src.batch_scraper --force      # Force re-scrape (ignore progress)

Architecture (from Plan 02-03):
- Scrapes Top Ratings page to discover dog URLs
- Creates single TokenBucketRateLimiter shared across all scrapers
- For each dog: scrapes stats, upserts to database, logs result
- Uses asyncio.gather with return_exceptions=True for fault tolerance
- Saves progress after each dog to enable resume
"""

import asyncio
import argparse
import logging
import json
import os
import sys
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path
from logging.handlers import RotatingFileHandler
from urllib.parse import urljoin, quote

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

from src.scrapers.greyhound_stats_scraper import GreyhoundStatsScraper
from src.storage.dog_stats import upsert_dog_stats
from src.utils.rate_limiter import TokenBucketRateLimiter


# Constants
BASE_URL = "https://greyhoundstats.co.uk"
TOP_RATINGS_URL = f"{BASE_URL}/top_ratings.php"
PROGRESS_FILE = ".scraper_progress.json"
LOG_DIR = "logs"
LOG_FILE = "batch_scraper.log"


class BatchScraperOrchestrator:
    """
    Orchestrates batch scraping of dog statistics.

    Handles:
    - Dog URL discovery from listing pages
    - Rate-limited scraping
    - Database storage
    - Progress tracking
    - Error handling and logging
    """

    def __init__(self, limit: Optional[int] = None, force: bool = False):
        """
        Initialize batch scraper.

        Args:
            limit: Optional limit on number of dogs to scrape (for testing)
            force: If True, ignore progress and re-scrape all dogs
        """
        self.limit = limit
        self.force = force
        self.rate_limiter = TokenBucketRateLimiter(rate=0.5, capacity=5)  # 2-sec delays
        self.stats = {
            'total_dogs': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }
        self.progress_data = self._load_progress()

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """
        Configure structured logging with file rotation.

        Logs to:
        - Console: INFO and above
        - File (logs/batch_scraper.log): DEBUG and above with daily rotation
        """
        # Create logs directory if needed
        Path(LOG_DIR).mkdir(exist_ok=True)

        # Configure root logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Remove any existing handlers
        logger.handlers.clear()

        # File handler with rotation (10MB max, keep 5 backups)
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, LOG_FILE),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    def _load_progress(self) -> Dict[str, Any]:
        """
        Load progress from .scraper_progress.json.

        Returns:
            dict: Progress data with 'date', 'processed', 'last_updated'
        """
        if not os.path.exists(PROGRESS_FILE) or self.force:
            return {
                'date': str(date.today()),
                'processed': [],
                'last_updated': None
            }

        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                progress = json.load(f)

            # Check if progress is from today
            if progress.get('date') == str(date.today()):
                logging.info(f"Resuming from previous run - {len(progress.get('processed', []))} dogs already processed")
                return progress
            else:
                logging.info("Previous progress is from different day - starting fresh")
                return {
                    'date': str(date.today()),
                    'processed': [],
                    'last_updated': None
                }

        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not load progress file: {e} - starting fresh")
            return {
                'date': str(date.today()),
                'processed': [],
                'last_updated': None
            }

    def _save_progress(self, dog_name: str, success: bool):
        """
        Save progress after processing a dog.

        Args:
            dog_name: Name of dog just processed
            success: Whether processing succeeded
        """
        self.progress_data['processed'].append({
            'dog_name': dog_name,
            'timestamp': datetime.now().isoformat(),
            'success': success
        })
        self.progress_data['last_updated'] = datetime.now().isoformat()

        try:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.progress_data, f, indent=2)
        except IOError as e:
            logging.error(f"Failed to save progress: {e}")

    def _is_processed(self, dog_name: str) -> bool:
        """
        Check if dog was already processed today.

        Args:
            dog_name: Dog name to check

        Returns:
            bool: True if already processed today
        """
        processed_names = [
            entry['dog_name']
            for entry in self.progress_data.get('processed', [])
        ]
        return dog_name in processed_names

    async def discover_dog_urls(self) -> List[str]:
        """
        Discover dog profile URLs from Top Ratings listing page.

        Returns:
            List[str]: List of dog profile URLs
        """
        logging.info(f"Discovering dog URLs from {TOP_RATINGS_URL}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # Navigate to Top Ratings page with rate limiting
                await self.rate_limiter.acquire()
                await page.goto(TOP_RATINGS_URL, wait_until='networkidle')

                # Get page content
                html = await page.content()

                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')

                # Find all links to dog profiles
                # Pattern: complete_runner_stats.php?dog=<dog_name>
                dog_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'complete_runner_stats.php?dog=' in href:
                        # Convert relative URL to absolute
                        if not href.startswith('http'):
                            href = urljoin(BASE_URL, href)
                        dog_links.append(href)

                # Remove duplicates while preserving order
                seen = set()
                unique_links = []
                for link in dog_links:
                    if link not in seen:
                        seen.add(link)
                        unique_links.append(link)

                logging.info(f"Discovered {len(unique_links)} dog URLs")

                # Apply limit if specified
                if self.limit:
                    unique_links = unique_links[:self.limit]
                    logging.info(f"Limited to first {self.limit} dogs")

                return unique_links

            except Exception as e:
                logging.error(f"Error discovering dog URLs: {e}")
                return []

            finally:
                await browser.close()

    async def scrape_dog(self, dog_url: str) -> Dict[str, Any]:
        """
        Scrape a single dog's statistics.

        Args:
            dog_url: URL to dog profile page

        Returns:
            dict: Result with 'success', 'dog_name', 'stats', 'error'
        """
        # Extract dog name from URL for logging
        match = re.search(r'dog=([^&]+)', dog_url)
        dog_name = match.group(1).replace('%20', ' ').replace('+', ' ') if match else 'Unknown'

        try:
            # Check if already processed (unless --force)
            if not self.force and self._is_processed(dog_name):
                logging.info(f"Skipping {dog_name} - already processed today")
                self.stats['skipped'] += 1
                return {
                    'success': True,
                    'skipped': True,
                    'dog_name': dog_name,
                    'stats': None,
                    'error': None
                }

            logging.info(f"Scraping {dog_name}...")

            # Create scraper and run
            scraper = GreyhoundStatsScraper(dog_url, self.rate_limiter)
            stats = await scraper.run()

            # Validate stats
            if not stats or not stats.get('dog_name'):
                raise ValueError("Invalid stats returned - missing dog_name")

            # Store in database
            success = upsert_dog_stats(stats['dog_name'], stats)

            if success:
                logging.info(f"[OK] Successfully scraped and stored {dog_name}")
                self.stats['successful'] += 1
                self._save_progress(dog_name, True)
                return {
                    'success': True,
                    'skipped': False,
                    'dog_name': dog_name,
                    'stats': stats,
                    'error': None
                }
            else:
                raise Exception("Database upsert failed")

        except Exception as e:
            logging.error(f"[FAIL] Failed to scrape {dog_name}: {e}")
            self.stats['failed'] += 1
            self._save_progress(dog_name, False)
            return {
                'success': False,
                'skipped': False,
                'dog_name': dog_name,
                'stats': None,
                'error': str(e)
            }

    async def run(self):
        """
        Run the batch scraping job.

        Main orchestration:
        1. Discover dog URLs from listing page
        2. Scrape each dog with rate limiting
        3. Store results in database
        4. Log summary statistics
        """
        self.stats['start_time'] = datetime.now()

        logging.info("=" * 60)
        logging.info("BATCH SCRAPER STARTED")
        logging.info(f"Date: {date.today()}")
        logging.info(f"Limit: {self.limit if self.limit else 'None (all dogs)'}")
        logging.info(f"Force: {self.force}")
        logging.info("=" * 60)

        # Discover dog URLs
        dog_urls = await self.discover_dog_urls()

        if not dog_urls:
            logging.error("No dog URLs discovered - aborting")
            return

        self.stats['total_dogs'] = len(dog_urls)

        # Scrape each dog
        # Use asyncio.gather with return_exceptions=True for fault tolerance
        logging.info(f"Processing {len(dog_urls)} dogs...")

        tasks = [self.scrape_dog(url) for url in dog_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results (count exceptions)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"Unhandled exception for dog {i+1}: {result}")
                self.stats['failed'] += 1

        # End time
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        # Print summary
        logging.info("=" * 60)
        logging.info("BATCH SCRAPER COMPLETED")
        logging.info(f"Total dogs: {self.stats['total_dogs']}")
        logging.info(f"Successful: {self.stats['successful']}")
        logging.info(f"Failed: {self.stats['failed']}")
        logging.info(f"Skipped (already processed): {self.stats['skipped']}")
        logging.info(f"Duration: {duration:.1f} seconds")
        logging.info(f"Average: {duration/self.stats['total_dogs']:.2f} sec/dog")
        logging.info("=" * 60)


async def main():
    """
    CLI entry point for batch scraper.

    Parses command-line arguments and runs the batch scraper.
    """
    parser = argparse.ArgumentParser(
        description='Batch scraper for dog statistics from greyhoundstats.co.uk'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of dogs to scrape (useful for testing)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-scrape all dogs (ignore progress file)'
    )

    args = parser.parse_args()

    # Create and run orchestrator
    orchestrator = BatchScraperOrchestrator(limit=args.limit, force=args.force)
    await orchestrator.run()


if __name__ == '__main__':
    asyncio.run(main())

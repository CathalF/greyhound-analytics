"""
Oddschecker Scraper for Greyhound Racing

Scrapes race fixtures and odds from oddschecker.com. Extracts:
- Race information (track, time, distance)
- Dog names and trap numbers (1-6)
- Bookmaker odds (decimal and fractional formats)

Extends BaseScraper for Playwright + stealth + rate limiting + retry logic.
"""

from bs4 import BeautifulSoup
from src.scrapers.base_scraper import BaseScraper
from src.utils.rate_limiter import TokenBucketRateLimiter
from typing import Dict, List, Optional
import re
from datetime import datetime


class OddscheckerScraper(BaseScraper):
    """
    Scraper for oddschecker.com greyhound racing race cards.

    Extracts complete race information including dogs, trap numbers, and odds
    from multiple bookmakers.

    URL Format: https://www.oddschecker.com/greyhounds/{track}/{time}/winner
    Example: https://www.oddschecker.com/greyhounds/harlow/18:11/winner

    Usage:
        rate_limiter = TokenBucketRateLimiter(rate=0.5)  # 2-second delays
        scraper = OddscheckerScraper(race_url, rate_limiter)
        data = await scraper.run()

    Returns dict with:
        {
            'race_id': str,           # Generated from track + time
            'track': str,             # e.g., "Harlow"
            'time': str,              # e.g., "18:11"
            'distance': Optional[str],# e.g., "500m" or None
            'dogs': [                 # List of dogs in race
                {
                    'name': str,      # Dog name from oddschecker
                    'trap': int,      # Trap number (1-6)
                    'bet_id': str     # Oddschecker's internal ID
                },
                ...
            ],
            'odds': [                 # List of odds records
                {
                    'dog_name': str,  # Dog name
                    'bookmaker': str, # Bookmaker code (e.g., "B3", "WH")
                    'fractional': str,# Fractional odds (e.g., "6/4")
                    'decimal': float  # Decimal odds (e.g., 2.5)
                },
                ...
            ]
        }
    """

    def __init__(self, race_url: str, rate_limiter: TokenBucketRateLimiter):
        """
        Initialize oddschecker scraper.

        Args:
            race_url: Full URL to race card (e.g., https://www.oddschecker.com/greyhounds/harlow/18:11/winner)
            rate_limiter: Rate limiter instance for request throttling
        """
        super().__init__(race_url, rate_limiter)

    async def parse(self, html: str) -> Dict:
        """
        Parse oddschecker race card HTML into structured data.

        Extracts:
        - Track name and race time from page title
        - Distance from page content (if available)
        - Dogs with trap numbers from table rows
        - Odds from all bookmakers for each dog

        Args:
            html: Raw HTML content from oddschecker race page

        Returns:
            Dict with race info, dogs list, and odds list

        Raises:
            ValueError: If required data (track, time, dogs) cannot be extracted
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Extract race info from page title
        # Title format: "Harlow 18:11 Betting Odds- Winner | Greyhounds | Oddschecker"
        title_tag = soup.find('title')
        if not title_tag:
            raise ValueError("Could not find page title")

        title = title_tag.get_text(strip=True)
        track, time = self._parse_track_and_time(title)

        # Generate race_id from track and time
        race_id = self._generate_race_id(track, time)

        # Extract distance (may not be available)
        distance = self._extract_distance(html)

        # Extract dogs from table rows
        dogs = self._extract_dogs(soup)
        if not dogs:
            raise ValueError(f"No dogs found in race card for {track} {time}")

        # Extract odds for all dogs
        odds = self._extract_odds(soup, dogs)

        return {
            'race_id': race_id,
            'track': track,
            'time': time,
            'distance': distance,
            'dogs': dogs,
            'odds': odds
        }

    def _parse_track_and_time(self, title: str) -> tuple[str, str]:
        """
        Extract track name and race time from page title.

        Args:
            title: Page title like "Harlow 18:11 Betting Odds- Winner | Greyhounds | Oddschecker"

        Returns:
            Tuple of (track_name, race_time)

        Raises:
            ValueError: If title format is unexpected
        """
        # Split at " Betting Odds" to get the "Track Time" part
        if " Betting Odds" not in title:
            raise ValueError(f"Unexpected title format: {title}")

        track_time_part = title.split(" Betting Odds")[0].strip()

        # Split at last space to separate track from time
        # Handle multi-word track names like "Belle Vue"
        parts = track_time_part.rsplit(" ", 1)
        if len(parts) != 2:
            raise ValueError(f"Could not parse track and time from: {track_time_part}")

        track, time = parts

        # Validate time format (HH:MM)
        if not re.match(r'^\d{2}:\d{2}$', time):
            raise ValueError(f"Invalid time format: {time}")

        return track, time

    def _generate_race_id(self, track: str, time: str) -> str:
        """
        Generate unique race ID from track and time.

        Format: {track_lowercase}_{time_HHMM}_{date_YYYYMMDD}

        Args:
            track: Track name
            time: Race time (HH:MM format)

        Returns:
            Race ID string
        """
        track_normalized = track.lower().replace(' ', '_')
        time_normalized = time.replace(':', '')
        date_str = datetime.now().strftime('%Y%m%d')

        return f"{track_normalized}_{time_normalized}_{date_str}"

    def _extract_distance(self, html: str) -> Optional[str]:
        """
        Extract race distance from HTML content.

        Looks for patterns like "500m", "380m", "695m".

        Args:
            html: Raw HTML content

        Returns:
            Distance string (e.g., "500m") or None if not found
        """
        # Search for distance pattern: 3-4 digits followed by 'm'
        matches = re.findall(r'\b(\d{3,4}m)\b', html)

        if matches:
            # Return most common distance (in case of multiple matches)
            from collections import Counter
            return Counter(matches).most_common(1)[0][0]

        return None

    def _extract_dogs(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract dogs and trap numbers from race card table.

        Each dog is a <tr> element with data-bname attribute.
        Trap number is extracted from the 'trap-cell' class element.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of dog dicts with name, trap, and bet_id
        """
        dog_rows = soup.select('tr[data-bname]')

        dogs = []
        for row in dog_rows:
            dog_name = row.get('data-bname')
            bet_id = row.get('data-bid')

            if not dog_name:
                continue

            # Extract actual trap number from trap-cell
            trap_cell = row.select_one('.trap-cell')
            trap = None
            if trap_cell:
                trap_text = trap_cell.get_text(strip=True)
                try:
                    trap = int(trap_text)
                except ValueError:
                    pass

            # Fallback: try cardnum class if trap-cell not found
            if trap is None:
                cardnum_cell = row.select_one('.cardnum')
                if cardnum_cell:
                    try:
                        trap = int(cardnum_cell.get_text(strip=True))
                    except ValueError:
                        pass

            dogs.append({
                'name': dog_name,
                'trap': trap,  # Actual trap number from page
                'bet_id': bet_id or ''
            })

        return dogs

    def _extract_odds(self, soup: BeautifulSoup, dogs: List[Dict]) -> List[Dict]:
        """
        Extract odds for all dogs from all bookmakers.

        Each dog row contains multiple <td> elements with data-o attribute
        representing odds from different bookmakers.

        Args:
            soup: BeautifulSoup parsed HTML
            dogs: List of dog dicts (for name lookup by row index)

        Returns:
            List of odds dicts with dog_name, bookmaker, fractional, and decimal odds
        """
        odds = []

        dog_rows = soup.select('tr[data-bname]')

        for row_index, row in enumerate(dog_rows):
            if row_index >= len(dogs):
                break  # Safety check

            dog_name = dogs[row_index]['name']

            # Find all odds cells in this row
            odds_cells = row.select('[data-o]')

            for cell in odds_cells:
                bookmaker = cell.get('data-bk')
                fractional_odds = cell.get('data-o')
                decimal_odds_str = cell.get('data-odig')

                # Skip if missing required data or if it's "SP" (Starting Price)
                if not bookmaker or not fractional_odds or not decimal_odds_str:
                    continue

                if fractional_odds == 'SP' or decimal_odds_str == '0':
                    # Skip Starting Price entries (odds not yet available)
                    continue

                try:
                    decimal_odds = float(decimal_odds_str)
                except ValueError:
                    # Skip if decimal odds can't be parsed
                    continue

                odds.append({
                    'dog_name': dog_name,
                    'bookmaker': bookmaker,
                    'fractional': fractional_odds,
                    'decimal': decimal_odds
                })

        return odds

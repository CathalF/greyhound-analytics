"""
Results Scraper for Greyhound Racing

Scrapes race results from oddschecker.com/greyhound-racing/results. Extracts:
- Finishing positions (1st through 6th)
- Dog names in finish order
- Starting prices (SP) if available
- Finishing times if available

Extends BaseScraper for Playwright + stealth + rate limiting + retry logic.
"""

from bs4 import BeautifulSoup
from src.scrapers.base_scraper import BaseScraper
from src.utils.rate_limiter import TokenBucketRateLimiter
from src.storage.dog_matcher import match_dog_to_stats
from typing import Dict, List, Optional
import re
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Results page URL
RESULTS_URL = "https://www.oddschecker.com/greyhound-racing/results"


class ResultsScraper(BaseScraper):
    """
    Scraper for oddschecker.com greyhound racing results.

    Extracts completed race results including finishing positions, times, and SP.

    URL: https://www.oddschecker.com/greyhound-racing/results

    Usage:
        rate_limiter = TokenBucketRateLimiter(rate=0.5)  # 2-second delays
        scraper = ResultsScraper(rate_limiter)
        results = await scraper.run()

    Returns list of result dicts:
        [
            {
                'track': 'Hove',
                'time': '19:42',
                'positions': [
                    {'position': 1, 'dog_name': 'Ballymac Doris', 'sp': 2.5, 'time': '29.45'},
                    {'position': 2, 'dog_name': 'Swift Runner', 'sp': 4.0, 'time': '29.67'},
                    ...
                ]
            },
            ...
        ]
    """

    def __init__(self, rate_limiter: TokenBucketRateLimiter, url: str = RESULTS_URL):
        """
        Initialize results scraper.

        Args:
            rate_limiter: Rate limiter instance for request throttling
            url: Results page URL (defaults to oddschecker greyhound results)
        """
        super().__init__(url, rate_limiter)

    async def parse(self, html: str) -> List[Dict]:
        """
        Parse oddschecker results page HTML into structured data.

        Extracts all completed race results from today's results page.

        Args:
            html: Raw HTML content from oddschecker results page

        Returns:
            List of result dictionaries with track, time, and positions
        """
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Find all race result sections
        # Oddschecker groups results by track with race times
        race_sections = self._find_race_sections(soup)

        for section in race_sections:
            try:
                result = self._parse_race_section(section)
                if result and result.get('positions'):
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error parsing race section: {e}")
                continue

        logger.info(f"Parsed {len(results)} race results from results page")
        return results

    def _find_race_sections(self, soup: BeautifulSoup) -> List:
        """
        Find all race result sections on the page.

        Looks for result containers that hold individual race results.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of BeautifulSoup elements containing race results
        """
        sections = []

        # Look for result cards/containers
        # Try multiple selectors as oddschecker structure may vary
        selectors = [
            '.race-result',
            '.result-card',
            '[data-race-result]',
            '.ResultsTable',
            'table.results-table',
            '.meeting-results article',
            '.race-results-container'
        ]

        for selector in selectors:
            found = soup.select(selector)
            if found:
                sections.extend(found)
                break

        # Fallback: Look for tables with position data
        if not sections:
            tables = soup.find_all('table')
            for table in tables:
                if self._looks_like_result_table(table):
                    sections.append(table)

        # Alternative: Look for result rows grouped by track/time headers
        if not sections:
            # Find headers that indicate tracks
            headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'\d{2}:\d{2}'))
            for header in headers:
                # Get the next sibling table or list
                next_elem = header.find_next(['table', 'ul', 'ol', 'div'])
                if next_elem and self._looks_like_result_table(next_elem):
                    sections.append({
                        'header': header,
                        'content': next_elem
                    })

        return sections

    def _looks_like_result_table(self, element) -> bool:
        """
        Check if an element looks like a race results table.

        Args:
            element: BeautifulSoup element to check

        Returns:
            True if element appears to contain race results
        """
        text = element.get_text().lower()
        # Results typically have position numbers and SP
        has_positions = any(f'{i}st' in text or f'{i}nd' in text or f'{i}rd' in text or f'{i}th' in text
                          for i in range(1, 7))
        has_sp = 'sp' in text or 'starting price' in text or bool(re.search(r'\d+/\d+', text))
        has_dogs = bool(re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+', element.get_text()))

        return has_positions or (has_sp and has_dogs)

    def _parse_race_section(self, section) -> Optional[Dict]:
        """
        Parse a single race result section.

        Args:
            section: BeautifulSoup element containing one race's results

        Returns:
            Dict with track, time, and positions list, or None if parsing fails
        """
        result = {
            'track': None,
            'time': None,
            'positions': []
        }

        # Handle dict format from header+content pairing
        if isinstance(section, dict):
            header = section.get('header')
            content = section.get('content')

            if header:
                header_text = header.get_text(strip=True)
                result['track'], result['time'] = self._extract_track_and_time(header_text)

            if content:
                result['positions'] = self._extract_positions(content)
        else:
            # Extract track and time from section
            # Look for track name and time pattern
            section_text = section.get_text()

            # Find track name (usually appears before time)
            track, time = self._extract_track_and_time_from_section(section)
            result['track'] = track
            result['time'] = time

            # Extract positions
            result['positions'] = self._extract_positions(section)

        return result if result['positions'] else None

    def _extract_track_and_time(self, text: str) -> tuple:
        """
        Extract track name and race time from text.

        Args:
            text: Text containing track and time info

        Returns:
            Tuple of (track_name, race_time)
        """
        track = None
        time = None

        # Find time pattern HH:MM
        time_match = re.search(r'(\d{2}:\d{2})', text)
        if time_match:
            time = time_match.group(1)

        # Track is usually everything before the time
        if time_match:
            track = text[:time_match.start()].strip()
            # Clean up track name
            track = re.sub(r'[^\w\s]', '', track).strip()

        return track, time

    def _extract_track_and_time_from_section(self, section) -> tuple:
        """
        Extract track name and time from a result section element.

        Args:
            section: BeautifulSoup element

        Returns:
            Tuple of (track_name, race_time)
        """
        track = None
        time = None

        # Look for specific elements containing track/time
        track_elem = section.select_one('.track-name, .venue, [data-track]')
        if track_elem:
            track = track_elem.get_text(strip=True)

        time_elem = section.select_one('.race-time, .time, [data-time]')
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            time_match = re.search(r'(\d{2}:\d{2})', time_text)
            if time_match:
                time = time_match.group(1)

        # Fallback: search entire section text
        if not track or not time:
            section_text = section.get_text()
            fallback_track, fallback_time = self._extract_track_and_time(section_text)
            track = track or fallback_track
            time = time or fallback_time

        return track, time

    def _extract_positions(self, section) -> List[Dict]:
        """
        Extract finishing positions from a result section.

        Args:
            section: BeautifulSoup element containing result positions

        Returns:
            List of position dictionaries with dog_name, position, sp, time
        """
        positions = []

        # Try to find result rows
        rows = section.select('tr, li, .result-row, [data-position]')

        for row in rows:
            position_data = self._parse_position_row(row)
            if position_data:
                positions.append(position_data)

        # Sort by position
        positions.sort(key=lambda x: x.get('position', 99))

        return positions

    def _parse_position_row(self, row) -> Optional[Dict]:
        """
        Parse a single position row from results.

        Args:
            row: BeautifulSoup element containing one position

        Returns:
            Dict with position, dog_name, sp, time or None if parsing fails
        """
        row_text = row.get_text(strip=True)

        # Extract position number
        position = None
        position_match = re.search(r'^(\d)[st|nd|rd|th]?', row_text)
        if position_match:
            position = int(position_match.group(1))
        else:
            # Try data attribute
            pos_attr = row.get('data-position') or row.get('data-pos')
            if pos_attr:
                try:
                    position = int(pos_attr)
                except ValueError:
                    pass

        if not position or position < 1 or position > 6:
            return None

        # Extract dog name - look for capitalized words
        dog_name = None
        name_elem = row.select_one('.dog-name, .runner-name, .selection-name, a')
        if name_elem:
            dog_name = name_elem.get_text(strip=True)
        else:
            # Try to find dog name in row text
            # Dog names are typically 2-3 capitalized words
            name_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', row.get_text())
            if name_match:
                dog_name = name_match.group(1)

        if not dog_name:
            return None

        # Extract SP (starting price)
        sp = None
        sp_match = re.search(r'(\d+)/(\d+)|(\d+\.\d+)', row_text)
        if sp_match:
            if sp_match.group(3):
                # Decimal odds
                sp = float(sp_match.group(3))
            elif sp_match.group(1) and sp_match.group(2):
                # Fractional odds - convert to decimal
                num = int(sp_match.group(1))
                denom = int(sp_match.group(2))
                sp = (num / denom) + 1

        # Also check for SP in specific element
        sp_elem = row.select_one('.sp, .starting-price, [data-sp]')
        if sp_elem and not sp:
            sp_text = sp_elem.get_text(strip=True)
            sp_match = re.search(r'(\d+)/(\d+)|(\d+\.\d+)', sp_text)
            if sp_match:
                if sp_match.group(3):
                    sp = float(sp_match.group(3))
                elif sp_match.group(1) and sp_match.group(2):
                    num = int(sp_match.group(1))
                    denom = int(sp_match.group(2))
                    sp = (num / denom) + 1

        # Extract finishing time
        finish_time = None
        time_match = re.search(r'(\d{2}\.\d{2})', row_text)
        if time_match:
            finish_time = time_match.group(1)

        return {
            'position': position,
            'dog_name': dog_name,
            'sp': sp,
            'time': finish_time
        }


async def scrape_results_page(rate_limiter: Optional[TokenBucketRateLimiter] = None) -> List[Dict]:
    """
    Get all results from today's oddschecker results page.

    Convenience function that creates scraper and runs it.

    Args:
        rate_limiter: Optional rate limiter (creates default if not provided)

    Returns:
        List of result dictionaries

    Example:
        results = await scrape_results_page()
        print(f"Found {len(results)} race results")
    """
    if rate_limiter is None:
        rate_limiter = TokenBucketRateLimiter(rate=0.5)

    scraper = ResultsScraper(rate_limiter)

    try:
        results = await scraper.run()
        return results
    except Exception as e:
        logger.error(f"Error scraping results page: {e}")
        return []


async def scrape_race_result(track: str, race_time: str, rate_limiter: Optional[TokenBucketRateLimiter] = None) -> Optional[Dict]:
    """
    Get result for a specific race.

    Scrapes results page and filters for the specific track and time.

    Args:
        track: Track name (e.g., 'Hove')
        race_time: Race time in HH:MM format (e.g., '19:42')
        rate_limiter: Optional rate limiter

    Returns:
        Result dict for specific race or None if not found

    Example:
        result = await scrape_race_result('Hove', '19:42')
        if result:
            winner = result['positions'][0]['dog_name']
            print(f"Winner: {winner}")
    """
    results = await scrape_results_page(rate_limiter)

    # Normalize track name for comparison
    track_normalized = track.lower().replace(' ', '').replace('-', '')

    for result in results:
        result_track = (result.get('track') or '').lower().replace(' ', '').replace('-', '')
        result_time = result.get('time')

        if result_track == track_normalized and result_time == race_time:
            return result

    logger.info(f"No result found for {track} at {race_time}")
    return None


def match_result_to_race(result: Dict, race_id: str) -> List[Dict]:
    """
    Match scraped dogs to database dogs for a race.

    Uses fuzzy matching from dog_matcher to link result dog names
    to existing dog_ids in the database.

    Args:
        result: Scraped result dict with positions
        race_id: Database race ID to match against

    Returns:
        List of matched result records ready for database insertion:
        [
            {
                'dog_id': 'ballymac-doris',
                'position': 1,
                'finishing_time': '29.45',
                'starting_price': 2.5
            },
            ...
        ]

    Example:
        result = await scrape_race_result('Hove', '19:42')
        matched = match_result_to_race(result, 'hove_1942_20260115')
        insert_race_results('hove_1942_20260115', matched)
    """
    matched_results = []

    for pos in result.get('positions', []):
        dog_name = pos.get('dog_name')
        if not dog_name:
            continue

        # Try to match dog name to database
        dog_id, confidence = match_dog_to_stats(dog_name)

        if dog_id and confidence > 0:
            matched_results.append({
                'dog_id': dog_id,
                'position': pos.get('position'),
                'finishing_time': pos.get('time'),
                'starting_price': pos.get('sp')
            })
        else:
            logger.warning(f"Could not match dog '{dog_name}' to database")

    return matched_results


# Synchronous wrapper for testing
def scrape_results_page_sync() -> List[Dict]:
    """
    Synchronous wrapper for scrape_results_page.

    For use in non-async contexts or testing.

    Returns:
        List of result dictionaries
    """
    import asyncio
    return asyncio.run(scrape_results_page())

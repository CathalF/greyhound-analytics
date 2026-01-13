"""
Greyhound Stats Scraper

Scrapes dog statistics from greyhoundstats.co.uk following the data access strategy
from research_notes.md (Phase 02-01). Extracts dog performance data including
race history, summary statistics, and derives track/distance/grade preferences.

Architecture:
- Extends BaseScraper (Playwright + stealth + rate limiting from Phase 1)
- Uses BeautifulSoup for HTML parsing
- Returns structured dict matching Dog model JSONB stats format
- Handles missing data gracefully (no crashes on optional fields)
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.rate_limiter import TokenBucketRateLimiter


class GreyhoundStatsScraper(BaseScraper):
    """
    Scraper for individual dog statistics from greyhoundstats.co.uk.

    Extracts:
    - Summary stats: runs, wins, win rate
    - Race history: last 10-20 races with full details
    - Derived stats: track preferences, distance stats, grade stats
    - Latest rating: most recent Chester Rating

    URL Pattern: https://greyhoundstats.co.uk/complete_runner_stats.php?dog={dog_name}

    Args:
        dog_url (str): URL to the dog's profile page
        rate_limiter (TokenBucketRateLimiter): Rate limiter for respectful scraping

    Example:
        rate_limiter = TokenBucketRateLimiter(rate=0.5)  # 2-sec delays
        scraper = GreyhoundStatsScraper(
            'https://greyhoundstats.co.uk/complete_runner_stats.php?dog=Proper%20Heiress',
            rate_limiter
        )
        stats = await scraper.run()
    """

    def __init__(self, dog_url: str, rate_limiter: TokenBucketRateLimiter):
        super().__init__(dog_url, rate_limiter)

    async def parse(self, html: str) -> Dict[str, Any]:
        """
        Parse dog profile HTML into structured statistics.

        Extracts data from three main sections:
        1. Summary table: runs, wins, win rate
        2. Race history table: detailed race records
        3. Derived statistics: calculated from race history

        Args:
            html (str): Raw HTML from dog profile page

        Returns:
            dict: Structured dog statistics in format:
                {
                    'dog_name': str,
                    'runs': int,
                    'wins': int,
                    'win_rate': float,
                    'recent_form': List[dict],  # Last 10 races
                    'track_stats': Dict[str, dict],
                    'distance_stats': Dict[str, dict],
                    'grade_stats': Dict[str, dict],
                    'latest_rating': Optional[int]
                }
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Extract dog name from page title or header
        dog_name = self._extract_dog_name(soup)

        # Extract summary statistics (Table 2 in research notes)
        summary_stats = self._extract_summary_stats(soup)

        # Extract race history (Table 3 in research notes)
        race_history = self._extract_race_history(soup)

        # Calculate derived statistics
        track_stats = self._calculate_track_stats(race_history)
        distance_stats = self._calculate_distance_stats(race_history)
        grade_stats = self._calculate_grade_stats(race_history)

        # Get latest rating from most recent race
        latest_rating = race_history[0].get('rating') if race_history else None

        return {
            'dog_name': dog_name,
            'runs': summary_stats.get('runs'),
            'wins': summary_stats.get('wins'),
            'win_rate': summary_stats.get('win_rate'),
            'recent_form': race_history[:10],  # Last 10 races
            'track_stats': track_stats,
            'distance_stats': distance_stats,
            'grade_stats': grade_stats,
            'latest_rating': latest_rating
        }

    def _extract_dog_name(self, soup: BeautifulSoup) -> str:
        """
        Extract dog name from page.

        Falls back to URL parameter if not found in HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            str: Dog name
        """
        # Try to find dog name in page content
        # Look for heading or title containing the dog name
        title = soup.find('title')
        if title and title.text:
            # Pattern: "Greyhound Stats - Dog Name"
            match = re.search(r'Greyhound Stats.*?-\s*(.+)', title.text)
            if match:
                return match.group(1).strip()

        # Fallback: extract from URL parameter
        match = re.search(r'dog=([^&]+)', self.url)
        if match:
            return match.group(1).replace('%20', ' ').replace('+', ' ')

        return 'Unknown Dog'

    def _extract_summary_stats(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract summary statistics from Table 2.

        Looks for table with headers: Runs, Wins, Win %

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            dict: {'runs': int, 'wins': int, 'win_rate': float}
        """
        tables = soup.find_all('table')

        # Summary table is typically the 2nd table (index 1)
        # But we'll search for the one with "Runs", "Wins", "Win %" headers
        for table in tables:
            rows = table.find_all('tr')
            if not rows:
                continue

            # Check if this is the summary table
            header_cells = rows[0].find_all(['th', 'td'])
            headers = [cell.text.strip() for cell in header_cells]

            if 'Runs' in headers and 'Wins' in headers:
                # Found the summary table
                if len(rows) > 1:
                    data_cells = rows[1].find_all(['th', 'td'])
                    data = [cell.text.strip() for cell in data_cells]

                    try:
                        runs_idx = headers.index('Runs')
                        wins_idx = headers.index('Wins')
                        win_rate_idx = headers.index('Win %') if 'Win %' in headers else None

                        return {
                            'runs': int(data[runs_idx]) if runs_idx < len(data) else None,
                            'wins': int(data[wins_idx]) if wins_idx < len(data) else None,
                            'win_rate': float(data[win_rate_idx]) if win_rate_idx and win_rate_idx < len(data) else None
                        }
                    except (ValueError, IndexError) as e:
                        # Handle parsing errors gracefully
                        pass

        # Return None values if not found
        return {'runs': None, 'wins': None, 'win_rate': None}

    def _extract_race_history(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract race history from Table 3.

        Expected columns: Date, Track, Trap, Dog, Grade, Distance, SP, Finish,
                         Sectional, Actual Time, Going, Calc. Time, Chester Rating, Trainer

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List[dict]: List of race records, most recent first
        """
        tables = soup.find_all('table')
        races = []

        # Race history is typically the 3rd table (index 2)
        # Look for table with "Date", "Track", "Distance" headers
        for table in tables:
            rows = table.find_all('tr')
            if not rows:
                continue

            # Get headers
            header_cells = rows[0].find_all(['th', 'td'])
            headers = [cell.text.strip() for cell in header_cells]

            # Check if this is the race history table
            if 'Date' in headers and 'Track' in headers and 'Distance' in headers:
                # Process each race row
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all(['th', 'td'])
                    if len(cells) < len(headers):
                        continue  # Skip malformed rows

                    race = self._parse_race_row(headers, cells)
                    if race:
                        races.append(race)

                break  # Found the race history table

        return races

    def _parse_race_row(self, headers: List[str], cells: List) -> Optional[Dict[str, Any]]:
        """
        Parse a single race history row.

        Handles missing/optional fields gracefully.

        Args:
            headers: List of column headers
            cells: List of table cells

        Returns:
            dict or None: Race record or None if invalid
        """
        try:
            race = {}

            for i, header in enumerate(headers):
                if i >= len(cells):
                    race[header.lower().replace(' ', '_')] = None
                    continue

                cell_text = cells[i].text.strip()

                # Map headers to fields with appropriate type conversion
                if header == 'Date':
                    race['date'] = self._parse_date(cell_text)
                elif header == 'Track':
                    race['track'] = cell_text or None
                elif header == 'Trap':
                    race['trap'] = int(cell_text) if cell_text and cell_text.isdigit() else None
                elif header == 'Dog':
                    race['dog'] = cell_text or None
                elif header == 'Grade':
                    race['grade'] = cell_text or None
                elif header == 'Distance':
                    race['distance'] = cell_text or None
                elif header == 'SP':
                    race['sp'] = cell_text or None
                elif header == 'Finish':
                    race['finish_position'] = int(cell_text) if cell_text and cell_text.isdigit() else None
                elif header == 'Sectional':
                    race['sectional'] = self._parse_float(cell_text)
                elif header == 'Actual Time':
                    race['actual_time'] = self._parse_float(cell_text)
                elif header == 'Going':
                    race['going'] = cell_text or None
                elif header == 'Calc. Time' or header == 'Calc Time':
                    race['calc_time'] = self._parse_float(cell_text)
                elif 'Rating' in header:  # Chester Rating or Rating
                    race['rating'] = int(cell_text) if cell_text and cell_text.isdigit() else None
                elif header == 'Trainer':
                    race['trainer'] = cell_text or None

            # Validate required fields
            if race.get('date') and race.get('track'):
                return race

        except Exception as e:
            # Log error but don't crash - return None for invalid rows
            pass

        return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse date from DD/MM/YYYY format to ISO format (YYYY-MM-DD).

        Args:
            date_str: Date string in DD/MM/YYYY format

        Returns:
            str or None: ISO format date string or None if invalid
        """
        if not date_str:
            return None

        try:
            # Parse DD/MM/YYYY format
            dt = datetime.strptime(date_str, '%d/%m/%Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            return None

    def _parse_float(self, value_str: str) -> Optional[float]:
        """
        Parse float value, handling empty strings.

        Args:
            value_str: String representation of float

        Returns:
            float or None
        """
        if not value_str:
            return None

        try:
            return float(value_str)
        except ValueError:
            return None

    def _calculate_track_stats(self, races: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate performance statistics by track.

        Args:
            races: List of race records

        Returns:
            dict: Track name -> {runs, wins, win_rate, avg_rating}
        """
        track_stats = {}

        for race in races:
            track = race.get('track')
            if not track:
                continue

            if track not in track_stats:
                track_stats[track] = {
                    'runs': 0,
                    'wins': 0,
                    'ratings': []
                }

            track_stats[track]['runs'] += 1

            # Check if won (finish_position == 1)
            if race.get('finish_position') == 1:
                track_stats[track]['wins'] += 1

            # Collect ratings for average calculation
            rating = race.get('rating')
            if rating is not None:
                track_stats[track]['ratings'].append(rating)

        # Calculate averages and clean up
        for track, stats in track_stats.items():
            stats['win_rate'] = (stats['wins'] / stats['runs'] * 100) if stats['runs'] > 0 else 0
            stats['avg_rating'] = sum(stats['ratings']) / len(stats['ratings']) if stats['ratings'] else None
            del stats['ratings']  # Don't store raw list

        return track_stats

    def _calculate_distance_stats(self, races: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate performance statistics by distance.

        Args:
            races: List of race records

        Returns:
            dict: Distance -> {runs, wins, win_rate}
        """
        distance_stats = {}

        for race in races:
            distance = race.get('distance')
            if not distance:
                continue

            if distance not in distance_stats:
                distance_stats[distance] = {
                    'runs': 0,
                    'wins': 0
                }

            distance_stats[distance]['runs'] += 1

            if race.get('finish_position') == 1:
                distance_stats[distance]['wins'] += 1

        # Calculate win rates
        for distance, stats in distance_stats.items():
            stats['win_rate'] = (stats['wins'] / stats['runs'] * 100) if stats['runs'] > 0 else 0

        return distance_stats

    def _calculate_grade_stats(self, races: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate performance statistics by grade.

        Args:
            races: List of race records

        Returns:
            dict: Grade -> {runs, wins, win_rate}
        """
        grade_stats = {}

        for race in races:
            grade = race.get('grade')
            if not grade:
                continue

            if grade not in grade_stats:
                grade_stats[grade] = {
                    'runs': 0,
                    'wins': 0
                }

            grade_stats[grade]['runs'] += 1

            if race.get('finish_position') == 1:
                grade_stats[grade]['wins'] += 1

        # Calculate win rates
        for grade, stats in grade_stats.items():
            stats['win_rate'] = (stats['wins'] / stats['runs'] * 100) if stats['runs'] > 0 else 0

        return grade_stats

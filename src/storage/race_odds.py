"""
Race and Odds Storage Layer

Provides functions for storing and retrieving races, odds, and linking dogs to races.
Supports upsert operations and queries for upcoming races and odds data.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import Json
from src.storage.db import get_db


def upsert_race(race_dict: Dict[str, Any]) -> bool:
    """
    Insert new race or update existing race.

    Uses PostgreSQL's INSERT ... ON CONFLICT (DO UPDATE) for atomic upsert.

    Args:
        race_dict: Race data dictionary with keys:
            - race_id: Unique race identifier
            - track: Track name
            - time: Race time (str format "HH:MM" or datetime)
            - distance: Distance (optional, can be None)

    Returns:
        bool: True if upsert succeeded, False otherwise

    Example:
        race = {
            'race_id': 'harlow_1811_20260114',
            'track': 'Harlow',
            'time': '18:11',
            'distance': '500m'
        }
        success = upsert_race(race)
    """
    db = get_db()

    race_id = race_dict.get('race_id')
    track_name = race_dict.get('track')
    race_time = race_dict.get('time')
    distance = race_dict.get('distance')

    if not race_id or not track_name or not race_time:
        print(f"Error: Missing required race fields (race_id, track, time)")
        return False

    # Convert time string to timestamp if needed
    if isinstance(race_time, str):
        # Assume today's date with the given time
        # Format: "HH:MM"
        try:
            today = datetime.now().date()
            time_parts = race_time.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            race_timestamp = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
        except (ValueError, IndexError) as e:
            print(f"Error parsing race time '{race_time}': {e}")
            return False
    else:
        race_timestamp = race_time

    # Parse distance if present (e.g., "500m" → 500)
    distance_int = None
    if distance:
        try:
            # Remove 'm' suffix if present
            distance_str = distance.replace('m', '').strip()
            distance_int = int(distance_str)
        except (ValueError, AttributeError):
            # Invalid distance format, leave as NULL
            pass

    now = datetime.now()

    try:
        query = """
            INSERT INTO races (race_id, track_name, race_time, distance, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (race_id)
            DO UPDATE SET
                track_name = EXCLUDED.track_name,
                race_time = EXCLUDED.race_time,
                distance = EXCLUDED.distance,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at
        """

        params = (
            race_id,
            track_name,
            race_timestamp,
            distance_int,
            'scheduled',  # Default status
            now,
            now
        )

        db.execute_query(query, params, fetch=False)
        return True

    except psycopg2.Error as e:
        print(f"Error upserting race '{race_id}': {e}")
        return False


def link_dog_to_race(dog_id: str, race_id: str, trap_number: int) -> bool:
    """
    Link dog to race by updating race_id and trap_number fields.

    Updates an existing dog record to associate it with a race.

    Args:
        dog_id: Dog ID (primary key)
        race_id: Race ID to link
        trap_number: Trap number (1-8, Irish tracks can have 7-8 dogs)

    Returns:
        bool: True if update succeeded, False otherwise

    Example:
        success = link_dog_to_race('rathbally-bolger', 'harlow_1811_20260114', 1)
    """
    db = get_db()

    if not dog_id or not race_id:
        print(f"Error: Missing required fields (dog_id, race_id)")
        return False

    if trap_number < 1 or trap_number > 8:
        print(f"Error: Invalid trap_number {trap_number} (must be 1-8)")
        return False

    try:
        query = """
            UPDATE dogs
            SET race_id = %s, trap_number = %s
            WHERE dog_id = %s
        """

        params = (race_id, trap_number, dog_id)

        db.execute_query(query, params, fetch=False)
        return True

    except psycopg2.Error as e:
        print(f"Error linking dog '{dog_id}' to race '{race_id}': {e}")
        return False


def upsert_odds(odds_list: List[Dict[str, Any]]) -> int:
    """
    Insert or update multiple odds records.

    Batches odds insertion for efficiency. Uses unique odds_id to prevent duplicates.

    Args:
        odds_list: List of odds dictionaries with keys:
            - race_id: Race ID
            - dog_id: Dog ID
            - bookmaker: Bookmaker code (e.g., "B3", "WH")
            - decimal: Decimal odds (float)
            - fractional: Fractional odds (str, e.g., "6/4")
            - timestamp: When odds were scraped (datetime, optional - defaults to now)

    Returns:
        int: Number of odds records successfully inserted/updated

    Example:
        odds = [
            {
                'race_id': 'harlow_1811_20260114',
                'dog_id': 'rathbally-bolger',
                'bookmaker': 'B3',
                'decimal': 2.5,
                'fractional': '6/4'
            },
            ...
        ]
        count = upsert_odds(odds)
        print(f"Inserted {count} odds records")
    """
    db = get_db()

    if not odds_list:
        return 0

    inserted_count = 0
    now = datetime.now()

    try:
        for odds_dict in odds_list:
            race_id = odds_dict.get('race_id')
            dog_id = odds_dict.get('dog_id')
            bookmaker = odds_dict.get('bookmaker')
            decimal_odds = odds_dict.get('decimal')
            fractional_odds = odds_dict.get('fractional')
            timestamp = odds_dict.get('timestamp', now)

            if not all([race_id, dog_id, bookmaker, decimal_odds, fractional_odds]):
                print(f"Warning: Skipping odds record with missing fields")
                continue

            # Generate unique odds_id
            # Format: {race_id}_{dog_id}_{bookmaker}_{timestamp_epoch}
            timestamp_str = int(timestamp.timestamp())
            odds_id = f"{race_id}_{dog_id}_{bookmaker}_{timestamp_str}"

            query = """
                INSERT INTO odds (odds_id, race_id, dog_id, bookmaker, decimal_odds, fractional_odds, timestamp, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (odds_id)
                DO UPDATE SET
                    decimal_odds = EXCLUDED.decimal_odds,
                    fractional_odds = EXCLUDED.fractional_odds,
                    timestamp = EXCLUDED.timestamp
            """

            params = (
                odds_id,
                race_id,
                dog_id,
                bookmaker,
                decimal_odds,
                fractional_odds,
                timestamp,
                now
            )

            db.execute_query(query, params, fetch=False)
            inserted_count += 1

        return inserted_count

    except psycopg2.Error as e:
        print(f"Error upserting odds (inserted {inserted_count} before error): {e}")
        return inserted_count


def get_race(race_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve race by ID.

    Args:
        race_id: Race ID

    Returns:
        Dict with race data or None if not found

    Example:
        race = get_race('harlow_1811_20260114')
        if race:
            print(f"{race['track_name']} at {race['race_time']}")
    """
    db = get_db()

    try:
        query = """
            SELECT race_id, track_name, race_time, distance, status, created_at, updated_at
            FROM races
            WHERE race_id = %s
        """

        results = db.execute_query(query, (race_id,), fetch=True)

        if results and len(results) > 0:
            return dict(results[0])
        else:
            return None

    except psycopg2.Error as e:
        print(f"Error retrieving race '{race_id}': {e}")
        return None


def get_race_odds(race_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all odds for a race.

    Args:
        race_id: Race ID

    Returns:
        List of odds dictionaries

    Example:
        odds = get_race_odds('harlow_1811_20260114')
        for odd in odds:
            print(f"{odd['dog_id']}: {odd['bookmaker']} offers {odd['fractional_odds']}")
    """
    db = get_db()

    try:
        query = """
            SELECT odds_id, race_id, dog_id, bookmaker, decimal_odds, fractional_odds, timestamp, created_at
            FROM odds
            WHERE race_id = %s
            ORDER BY dog_id, bookmaker
        """

        results = db.execute_query(query, (race_id,), fetch=True)

        return [dict(row) for row in results] if results else []

    except psycopg2.Error as e:
        print(f"Error retrieving odds for race '{race_id}': {e}")
        return []


def get_upcoming_races(hours_ahead: int = 2) -> List[Dict[str, Any]]:
    """
    Get races starting within the next N hours.

    Useful for refresh scraping (only update odds for imminent races).

    Args:
        hours_ahead: Number of hours to look ahead (default 2)

    Returns:
        List of race dictionaries

    Example:
        # Get races starting in next 2 hours
        active_races = get_upcoming_races(hours_ahead=2)
        for race in active_races:
            print(f"Upcoming: {race['track_name']} at {race['race_time']}")
    """
    db = get_db()

    try:
        now = datetime.now()
        end_time = now + timedelta(hours=hours_ahead)

        query = """
            SELECT race_id, track_name, race_time, distance, status, created_at, updated_at
            FROM races
            WHERE race_time BETWEEN %s AND %s
            ORDER BY race_time
        """

        results = db.execute_query(query, (now, end_time), fetch=True)

        return [dict(row) for row in results] if results else []

    except psycopg2.Error as e:
        print(f"Error retrieving upcoming races: {e}")
        return []


def get_race_with_dogs(race_id: str) -> Optional[Dict[str, Any]]:
    """
    Get race with all associated dogs.

    Performs JOIN to include dog names, trap numbers, and stats.

    Args:
        race_id: Race ID

    Returns:
        Dict with race data and 'dogs' list, or None if not found

    Example:
        race = get_race_with_dogs('harlow_1811_20260114')
        if race:
            print(f"Race: {race['track_name']} at {race['race_time']}")
            for dog in race['dogs']:
                print(f"  Trap {dog['trap_number']}: {dog['name']}")
    """
    db = get_db()

    try:
        # Get race info
        race = get_race(race_id)
        if not race:
            return None

        # Get dogs in this race
        query = """
            SELECT dog_id, name, trap_number, stats
            FROM dogs
            WHERE race_id = %s
            ORDER BY trap_number
        """

        results = db.execute_query(query, (race_id,), fetch=True)

        race['dogs'] = [dict(row) for row in results] if results else []

        return race

    except psycopg2.Error as e:
        print(f"Error retrieving race with dogs '{race_id}': {e}")
        return None


def update_race_status(race_id: str, status: str) -> bool:
    """
    Update race status field.

    Statuses: 'upcoming', 'imminent', 'complete'

    Args:
        race_id: Race ID
        status: New status value

    Returns:
        bool: True if update succeeded, False otherwise

    Example:
        update_race_status('harlow_1811_20260114', 'imminent')
    """
    db = get_db()

    valid_statuses = ['upcoming', 'imminent', 'complete', 'scheduled']
    if status not in valid_statuses:
        print(f"Warning: Invalid status '{status}' (valid: {valid_statuses})")

    try:
        query = """
            UPDATE races
            SET status = %s, updated_at = %s
            WHERE race_id = %s
        """

        params = (status, datetime.now(), race_id)

        db.execute_query(query, params, fetch=False)
        return True

    except psycopg2.Error as e:
        print(f"Error updating race status for '{race_id}': {e}")
        return False


def get_active_races() -> List[Dict[str, Any]]:
    """
    Get all active races (upcoming or imminent, not complete).

    Returns only races with status in ('upcoming', 'imminent') to avoid
    wasting resources refreshing completed races.

    Returns:
        List of race dictionaries

    Example:
        active = get_active_races()
        for race in active:
            print(f"{race['track_name']} at {race['race_time']}: {race['status']}")
    """
    db = get_db()

    try:
        query = """
            SELECT race_id, track_name, race_time, distance, status, created_at, updated_at
            FROM races
            WHERE status IN ('upcoming', 'imminent', 'scheduled')
            ORDER BY race_time
        """

        results = db.execute_query(query, fetch=True)

        return [dict(row) for row in results] if results else []

    except psycopg2.Error as e:
        print(f"Error retrieving active races: {e}")
        return []


def cleanup_old_races(hours_old: float = 1.0) -> Dict[str, int]:
    """
    Delete races and their associated odds that have already passed.

    Only removes races that are older than N hours AND have status='scheduled'
    (never ran). Completed races are preserved for historical analysis.

    Args:
        hours_old: Delete races older than this many hours (default 1 hour)

    Returns:
        Dict with counts: {'races_deleted': int, 'odds_deleted': int}

    Example:
        # Clean up races that finished more than 2 hours ago
        result = cleanup_old_races(hours_old=2.0)
        print(f"Deleted {result['races_deleted']} races and {result['odds_deleted']} odds")
    """
    db = get_db()

    cutoff_time = datetime.now() - timedelta(hours=hours_old)

    try:
        # First, count and delete odds for old scheduled races only
        odds_query = """
            DELETE FROM odds
            WHERE race_id IN (
                SELECT race_id FROM races WHERE race_time < %s AND status = 'scheduled'
            )
        """
        # Get count before delete
        count_odds_query = """
            SELECT COUNT(*) FROM odds
            WHERE race_id IN (
                SELECT race_id FROM races WHERE race_time < %s AND status = 'scheduled'
            )
        """
        odds_count_result = db.execute_query(count_odds_query, (cutoff_time,), fetch=True)
        odds_deleted = list(odds_count_result[0].values())[0] if odds_count_result else 0

        db.execute_query(odds_query, (cutoff_time,), fetch=False)

        # Then delete the old scheduled races only
        count_races_query = "SELECT COUNT(*) FROM races WHERE race_time < %s AND status = 'scheduled'"
        races_count_result = db.execute_query(count_races_query, (cutoff_time,), fetch=True)
        races_deleted = list(races_count_result[0].values())[0] if races_count_result else 0

        races_query = "DELETE FROM races WHERE race_time < %s AND status = 'scheduled'"
        db.execute_query(races_query, (cutoff_time,), fetch=False)

        return {
            'races_deleted': races_deleted,
            'odds_deleted': odds_deleted
        }

    except psycopg2.Error as e:
        print(f"Error cleaning up old races: {e}")
        return {'races_deleted': 0, 'odds_deleted': 0}


def mark_race_complete(race_id: str) -> bool:
    """
    Mark a race as complete to preserve it from cleanup.

    Updates race status to 'complete', keeping the race and associated odds
    in the database for historical analysis.

    Args:
        race_id: Race ID to mark as complete

    Returns:
        bool: True if update succeeded, False otherwise

    Example:
        # After recording race results
        success = mark_race_complete('harlow_1811_20260114')
        if success:
            print("Race marked as complete, will be preserved in database")
    """
    return update_race_status(race_id, 'complete')

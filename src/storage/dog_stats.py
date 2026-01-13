"""
Dog statistics storage layer.

Provides functions for storing and retrieving dog statistics from the database.
Supports upsert operations (insert new dogs or update existing) and queries for
finding stale dogs that need stats refresh.

Note: For Phase 2, dogs can exist without being assigned to a race (stats-only records).
The race_id field can be NULL for these dogs. Race assignment happens in Phase 3 when
we scrape race cards from oddschecker.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from psycopg2.extras import Json, RealDictCursor
import psycopg2

from src.storage.db import get_db


def upsert_dog_stats(dog_name: str, stats_dict: Dict[str, Any]) -> bool:
    """
    Insert new dog or update existing dog's statistics.

    Uses PostgreSQL's INSERT ... ON CONFLICT (DO UPDATE) pattern for atomic upsert.
    Creates a stats-only dog record with placeholder race_id and trap_number.
    Updates last_stats_update timestamp on every upsert.

    Args:
        dog_name (str): Dog's registered name (used as lookup key)
        stats_dict (dict): Statistics dictionary to store in JSONB field
            Expected keys: runs, wins, win_rate, recent_form, track_stats,
                          distance_stats, grade_stats, latest_rating

    Returns:
        bool: True if upsert succeeded, False otherwise

    Example:
        stats = {
            'runs': 32,
            'wins': 23,
            'win_rate': 71.87,
            'recent_form': [...],
            'track_stats': {...},
            'distance_stats': {...},
            'grade_stats': {...},
            'latest_rating': 144
        }
        success = upsert_dog_stats('Proper Heiress', stats)
    """
    db = get_db()

    # Generate dog_id from name (lowercase with hyphens)
    dog_id = dog_name.lower().replace(' ', '-')

    # For Phase 2, use NULL for race fields (stats-only dogs)
    # These will be populated in Phase 3 when we integrate with race cards
    race_id = None  # NULL indicates no race assignment yet
    trap_number = None  # NULL indicates no trap assignment yet

    # Current timestamp for stats update
    now = datetime.now()

    try:
        query = """
            INSERT INTO dogs (dog_id, name, race_id, trap_number, stats, last_stats_update, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (dog_id)
            DO UPDATE SET
                stats = EXCLUDED.stats,
                last_stats_update = EXCLUDED.last_stats_update,
                name = EXCLUDED.name
        """

        params = (
            dog_id,
            dog_name,
            race_id,
            trap_number,
            Json(stats_dict),  # Convert dict to JSONB
            now,
            now
        )

        db.execute_query(query, params, fetch=False)
        return True

    except psycopg2.Error as e:
        print(f"Error upserting dog stats for '{dog_name}': {e}")
        return False


def get_dog_stats(dog_name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve dog statistics by name.

    Args:
        dog_name (str): Dog's registered name

    Returns:
        dict or None: Dog record with stats, or None if not found
            {
                'dog_id': str,
                'name': str,
                'race_id': str,
                'trap_number': int,
                'stats': dict,
                'last_stats_update': datetime,
                'created_at': datetime
            }

    Example:
        dog = get_dog_stats('Proper Heiress')
        if dog:
            print(f"Win rate: {dog['stats']['win_rate']}%")
    """
    db = get_db()

    # Generate dog_id from name
    dog_id = dog_name.lower().replace(' ', '-')

    try:
        query = """
            SELECT dog_id, name, race_id, trap_number, stats, last_stats_update, created_at
            FROM dogs
            WHERE dog_id = %s
        """

        results = db.execute_query(query, (dog_id,), fetch=True)

        if results and len(results) > 0:
            return dict(results[0])  # Convert RealDictRow to dict
        else:
            return None

    except psycopg2.Error as e:
        print(f"Error retrieving dog stats for '{dog_name}': {e}")
        return None


def list_dogs_by_last_update(limit: int = 100, oldest_first: bool = True) -> List[Dict[str, Any]]:
    """
    List dogs sorted by last_stats_update timestamp.

    Useful for finding stale dogs that need stats refresh.

    Args:
        limit (int): Maximum number of dogs to return (default 100)
        oldest_first (bool): If True, returns oldest updates first (default).
                            If False, returns most recent updates first.

    Returns:
        List[dict]: List of dog records with basic info and last_stats_update
            [
                {
                    'dog_id': str,
                    'name': str,
                    'last_stats_update': datetime,
                    'stats': dict
                },
                ...
            ]

    Example:
        # Find 50 dogs with oldest stats (need refresh)
        stale_dogs = list_dogs_by_last_update(limit=50, oldest_first=True)
        for dog in stale_dogs:
            print(f"{dog['name']}: last updated {dog['last_stats_update']}")
    """
    db = get_db()

    try:
        order = 'ASC' if oldest_first else 'DESC'
        query = f"""
            SELECT dog_id, name, last_stats_update, stats
            FROM dogs
            WHERE last_stats_update IS NOT NULL
            ORDER BY last_stats_update {order}
            LIMIT %s
        """

        results = db.execute_query(query, (limit,), fetch=True)

        return [dict(row) for row in results] if results else []

    except psycopg2.Error as e:
        print(f"Error listing dogs by last update: {e}")
        return []


def get_all_dog_names() -> List[str]:
    """
    Get list of all dog names in the database.

    Useful for batch operations and checking which dogs are already tracked.

    Returns:
        List[str]: List of dog names

    Example:
        all_dogs = get_all_dog_names()
        print(f"Tracking {len(all_dogs)} dogs")
    """
    db = get_db()

    try:
        query = "SELECT name FROM dogs ORDER BY name"
        results = db.execute_query(query, fetch=True)

        return [row['name'] for row in results] if results else []

    except psycopg2.Error as e:
        print(f"Error getting all dog names: {e}")
        return []


def delete_dog_stats(dog_name: str) -> bool:
    """
    Delete a dog record from the database.

    Use with caution - this removes all statistics for the dog.

    Args:
        dog_name (str): Dog's registered name

    Returns:
        bool: True if deletion succeeded, False otherwise

    Example:
        deleted = delete_dog_stats('Old Retired Dog')
    """
    db = get_db()

    # Generate dog_id from name
    dog_id = dog_name.lower().replace(' ', '-')

    try:
        query = "DELETE FROM dogs WHERE dog_id = %s"
        db.execute_query(query, (dog_id,), fetch=False)
        return True

    except psycopg2.Error as e:
        print(f"Error deleting dog stats for '{dog_name}': {e}")
        return False


def count_dogs() -> int:
    """
    Count total number of dogs in the database.

    Returns:
        int: Number of dog records

    Example:
        total = count_dogs()
        print(f"Database contains {total} dogs")
    """
    db = get_db()

    try:
        query = "SELECT COUNT(*) as count FROM dogs"
        results = db.execute_query(query, fetch=True)

        if results and len(results) > 0:
            return results[0]['count']
        else:
            return 0

    except psycopg2.Error as e:
        print(f"Error counting dogs: {e}")
        return 0

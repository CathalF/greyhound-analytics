"""
Dog Name Matching Logic

Matches dog names from oddschecker.com to existing dogs in the stats database.
Uses normalized string matching to handle differences in capitalization, spacing, and formatting.

Matching Strategy (from Phase 3 Plan 1):
- Normalize both names: lowercase, remove spaces/hyphens/apostrophes
- Compare normalized strings for exact match
- Returns dog_id if match found, None otherwise
"""

from typing import Optional, Tuple, List
import psycopg2
from src.storage.db import get_db


def normalize_dog_name(name: str) -> str:
    """
    Normalize dog name for matching.

    Removes differences in:
    - Capitalization
    - Spacing
    - Hyphens
    - Apostrophes

    Args:
        name: Dog name to normalize

    Returns:
        Normalized name (lowercase, no spaces/hyphens/apostrophes)

    Example:
        normalize_dog_name("Rathbally Bolger")  # → "rathballybolger"
        normalize_dog_name("RATHBALLY BOLGER")  # → "rathballybolger"
        normalize_dog_name("Rathbally-Bolger")  # → "rathballybolger"
        normalize_dog_name("O'Reilly's Dog")    # → "oreillysdog"
    """
    return name.lower().replace(' ', '').replace('-', '').replace("'", '')


def get_all_dogs_for_matching() -> List[Tuple[str, str]]:
    """
    Get all dogs from database for name matching.

    Returns:
        List of (dog_id, name) tuples

    Example:
        dogs = get_all_dogs_for_matching()
        # [('proper-heiress', 'Proper Heiress'), ('old-fort-sizzler', 'Old Fort Sizzler'), ...]
    """
    db = get_db()

    try:
        query = "SELECT dog_id, name FROM dogs ORDER BY name"
        results = db.execute_query(query, fetch=True)

        if results:
            return [(row['dog_id'], row['name']) for row in results]
        else:
            return []

    except psycopg2.Error as e:
        print(f"Error fetching dogs for matching: {e}")
        return []


def match_dog_to_stats(oddschecker_dog_name: str) -> Tuple[Optional[str], float]:
    """
    Match oddschecker dog name to existing dog in stats database.

    Uses normalized string matching strategy:
    1. Normalize oddschecker name (lowercase, remove spaces/hyphens/apostrophes)
    2. Normalize each database dog name
    3. Compare normalized strings for exact match
    4. Return dog_id if match found, None if no match

    Args:
        oddschecker_dog_name: Dog name from oddschecker.com

    Returns:
        Tuple of (dog_id, confidence):
            - dog_id: Database dog_id if match found, None if no match
            - confidence: 1.0 if exact match, 0.0 if no match

    Example:
        # Exact match (different capitalization)
        dog_id, confidence = match_dog_to_stats("RATHBALLY BOLGER")
        # → ('rathbally-bolger', 1.0) if "Rathbally Bolger" exists in database

        # No match
        dog_id, confidence = match_dog_to_stats("Unknown Dog")
        # → (None, 0.0)
    """
    # Get all dogs from database
    all_dogs = get_all_dogs_for_matching()

    if not all_dogs:
        # No dogs in database
        return (None, 0.0)

    # Normalize the oddschecker name
    normalized_input = normalize_dog_name(oddschecker_dog_name)

    # Try to find exact match (normalized)
    for dog_id, db_name in all_dogs:
        normalized_db_name = normalize_dog_name(db_name)

        if normalized_input == normalized_db_name:
            # Exact match found (case-insensitive, ignoring spacing/hyphens)
            return (dog_id, 1.0)

    # No match found
    return (None, 0.0)


def match_dog_by_id(dog_id: str) -> Optional[str]:
    """
    Check if dog_id exists in database.

    Args:
        dog_id: Dog ID to check

    Returns:
        dog_id if exists, None otherwise

    Example:
        exists = match_dog_by_id('proper-heiress')
        # → 'proper-heiress' if exists, None if not found
    """
    db = get_db()

    try:
        query = "SELECT dog_id FROM dogs WHERE dog_id = %s"
        results = db.execute_query(query, (dog_id,), fetch=True)

        if results and len(results) > 0:
            return results[0]['dog_id']
        else:
            return None

    except psycopg2.Error as e:
        print(f"Error checking dog_id '{dog_id}': {e}")
        return None


def get_matching_stats(dog_name: str) -> Optional[dict]:
    """
    Get stats for a dog by matching name.

    Convenience function that combines matching and stats retrieval.

    Args:
        dog_name: Dog name from oddschecker

    Returns:
        Dict with dog info and stats if match found, None otherwise

    Example:
        stats = get_matching_stats("RATHBALLY BOLGER")
        if stats:
            print(f"Win rate: {stats['stats']['win_rate']}%")
    """
    dog_id, confidence = match_dog_to_stats(dog_name)

    if dog_id is None or confidence == 0.0:
        return None

    db = get_db()

    try:
        query = """
            SELECT dog_id, name, race_id, trap_number, stats, last_stats_update, created_at
            FROM dogs
            WHERE dog_id = %s
        """

        results = db.execute_query(query, (dog_id,), fetch=True)

        if results and len(results) > 0:
            return dict(results[0])
        else:
            return None

    except psycopg2.Error as e:
        print(f"Error retrieving matching stats for '{dog_name}': {e}")
        return None

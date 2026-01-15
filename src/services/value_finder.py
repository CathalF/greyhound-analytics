"""
Value Bet Identification Service

Core logic for identifying value betting opportunities by comparing
dog statistics (win rates) against bookmaker odds (implied probabilities).

Also provides functions for tracking value bets in bet_history table and
updating outcomes after race results are recorded.
"""

from typing import Tuple, List, Dict, Any, Optional
from datetime import datetime, timedelta
from src.storage.race_odds import get_race_with_dogs, get_race_odds, get_upcoming_races
from src.storage.race_results import record_value_bet, update_bet_outcome, get_betting_history, get_race_results
from src.storage.db import get_db
from collections import defaultdict
import logging

# Set up logging
logger = logging.getLogger(__name__)


# Configuration
VALUE_THRESHOLD = 1.2  # 20% edge minimum
STRONG_VALUE_THRESHOLD = 1.4  # 40% edge for strong highlights

# Top 5 bookmakers to display
TOP_BOOKMAKERS = ['B3', 'WH', 'PP', 'SK', 'BF']

# Bookmaker code to name mapping
BOOKMAKER_NAMES = {
    'B3': 'Bet365',
    'WH': 'William Hill',
    'PP': 'Paddy Power',
    'SK': 'Sky Bet',
    'BF': 'Betfred'
}


def calculate_value_score(dog_stats: Dict[str, Any], best_decimal_odds: float) -> Tuple[float, str]:
    """
    Calculate value score comparing dog's performance to odds.

    The value score represents the ratio of actual probability to implied probability.
    A score > 1.0 indicates value (odds are better than stats suggest).

    Args:
        dog_stats: Dictionary with dog statistics (must include 'win_rate')
        best_decimal_odds: Best decimal odds available across bookmakers

    Returns:
        Tuple of (score, explanation):
        - score > 1.0 = value bet (odds better than stats suggest)
        - score = 1.0 = fair odds
        - score < 1.0 = poor value (odds worse than stats suggest)
        - explanation: Human-readable explanation of the value

    Example:
        dog_stats = {'win_rate': 30.0}  # 30% win rate
        best_odds = 4.0  # Implies 25% probability
        score, explanation = calculate_value_score(dog_stats, best_odds)
        # score = 1.2 (30% / 25% = 1.2x value)
        # explanation = "Decent value: 30.0% win rate vs 25.0% implied"
    """
    # Get win rate from stats (stored as percentage, e.g., 71.87)
    win_rate_pct = dog_stats.get('win_rate', 0)

    # Handle edge cases
    if win_rate_pct <= 0 or best_decimal_odds <= 1.0:
        return (0.0, "Insufficient data for value calculation")

    # Convert win rate to decimal probability (0-1)
    win_rate = win_rate_pct / 100.0

    # Calculate implied probability from odds
    # Decimal odds of 4.0 implies 1/4 = 0.25 = 25% probability
    # Convert to float to handle Decimal types from database
    implied_probability = 1.0 / float(best_decimal_odds)

    # Value score = actual probability / implied probability
    # If dog has 30% win rate but odds imply 20%, score = 1.5 (good value)
    # If dog has 20% win rate but odds imply 25%, score = 0.8 (poor value)
    score = win_rate / implied_probability

    # Generate human-readable explanation
    if score >= STRONG_VALUE_THRESHOLD:
        explanation = f"Strong value: {win_rate_pct:.1f}% win rate vs {implied_probability*100:.1f}% implied by odds"
    elif score >= VALUE_THRESHOLD:
        explanation = f"Decent value: {win_rate_pct:.1f}% win rate vs {implied_probability*100:.1f}% implied by odds"
    elif score >= 1.0:
        explanation = f"Marginal value: {win_rate_pct:.1f}% win rate vs {implied_probability*100:.1f}% implied by odds"
    else:
        explanation = f"No value: {win_rate_pct:.1f}% win rate vs {implied_probability*100:.1f}% implied by odds"

    return (score, explanation)


def find_value_bets_for_race(race_id: str, record_bets: bool = False) -> List[Dict[str, Any]]:
    """
    Identify value bets for a specific race.

    Analyzes all dogs in the race, comparing their stats against available odds.
    Returns only dogs with value score >= VALUE_THRESHOLD (1.2).

    Args:
        race_id: Unique race identifier
        record_bets: If True, automatically records value bets to bet_history table
                    (only records if not already recorded for this race+dog)

    Returns:
        List of value bet dictionaries containing:
        - dog_id: Dog's unique ID
        - dog_name: Dog's name
        - trap_number: Starting trap (1-6)
        - win_rate: Dog's historical win rate (%)
        - best_odds: Best decimal odds available
        - value_score: Calculated value score
        - explanation: Human-readable explanation

    Example:
        value_bets = find_value_bets_for_race('harlow_1811_20260114')
        # [
        #   {
        #     'dog_id': 'proper-heiress',
        #     'dog_name': 'Proper Heiress',
        #     'trap_number': 1,
        #     'win_rate': 71.87,
        #     'best_odds': 2.5,
        #     'value_score': 1.44,
        #     'explanation': 'Strong value: 71.9% win rate vs 40.0% implied'
        #   }
        # ]
    """
    # Get race with dogs
    race = get_race_with_dogs(race_id)

    if not race:
        return []

    # Get all odds for this race
    all_odds = get_race_odds(race_id)

    # Group odds by dog_id
    odds_by_dog = defaultdict(list)
    for odd in all_odds:
        odds_by_dog[odd['dog_id']].append(odd)

    value_bets = []

    # Analyze each dog
    for dog in race.get('dogs', []):
        dog_id = dog['dog_id']
        stats = dog.get('stats', {})

        # Skip dogs without stats
        if not stats or 'win_rate' not in stats:
            continue

        # Get odds for this dog (filter to top bookmakers only)
        dog_odds = [odd for odd in odds_by_dog.get(dog_id, []) if odd['bookmaker'] in TOP_BOOKMAKERS]

        if not dog_odds:
            continue

        # Find best odds (highest decimal value)
        best_odds = max(dog_odds, key=lambda x: x['decimal_odds'])
        best_decimal_odds = best_odds['decimal_odds']

        # Calculate value score
        value_score, explanation = calculate_value_score(stats, best_decimal_odds)

        # Only include if meets value threshold
        if value_score >= VALUE_THRESHOLD:
            value_bets.append({
                'dog_id': dog_id,
                'dog_name': dog['name'],
                'trap_number': dog['trap_number'],
                'win_rate': stats['win_rate'],
                'best_odds': best_decimal_odds,
                'best_bookmaker': BOOKMAKER_NAMES.get(best_odds['bookmaker'], best_odds['bookmaker']),
                'value_score': round(value_score, 2),
                'explanation': explanation
            })

    # Sort by value score (descending - best value first)
    value_bets.sort(key=lambda x: x['value_score'], reverse=True)

    # Record bets to bet_history if requested
    if record_bets and value_bets:
        _record_value_bets(race_id, value_bets)

    return value_bets


def _record_value_bets(race_id: str, value_bets: List[Dict[str, Any]]) -> int:
    """
    Record value bets to bet_history table.

    Only records if not already recorded for this race+dog combination.

    Args:
        race_id: Race ID
        value_bets: List of value bet dictionaries

    Returns:
        int: Number of new bets recorded
    """
    db = get_db()
    recorded = 0

    for vb in value_bets:
        dog_id = vb['dog_id']

        # Check if already recorded for this race+dog
        check_query = """
            SELECT bet_id FROM bet_history
            WHERE race_id = %s AND dog_id = %s
            LIMIT 1
        """
        try:
            existing = db.execute_query(check_query, (race_id, dog_id), fetch=True)
            if existing:
                # Already recorded, skip
                continue
        except Exception as e:
            logger.warning(f"Error checking existing bet: {e}")
            continue

        # Record new bet
        bet_id = record_value_bet(
            race_id=race_id,
            dog_id=dog_id,
            value_score=vb['value_score'],
            best_odds=float(vb['best_odds']),
            best_bookmaker=vb['best_bookmaker']
        )

        if bet_id:
            recorded += 1
            logger.info(f"Recorded value bet: {dog_id} in {race_id} (score: {vb['value_score']})")

    return recorded


def get_all_value_bets(hours_ahead: int = 4) -> List[Dict[str, Any]]:
    """
    Scan all upcoming races and identify value bets.

    Useful for dashboard overview showing best opportunities across all races.

    Args:
        hours_ahead: Number of hours to look ahead for races (default 4)

    Returns:
        List of value bet dictionaries with race context added:
        - All fields from find_value_bets_for_race()
        - Plus: race_id, track_name, race_time

    Example:
        all_value_bets = get_all_value_bets(hours_ahead=4)
        # Returns value bets from all races in next 4 hours,
        # sorted by value score (best first)
    """
    # Get upcoming races
    races = get_upcoming_races(hours_ahead)

    all_value_bets = []

    for race in races:
        race_id = race['race_id']

        # Find value bets for this race
        value_bets = find_value_bets_for_race(race_id)

        # Add race context to each value bet
        for vb in value_bets:
            all_value_bets.append({
                **vb,
                'race_id': race_id,
                'track_name': race['track_name'],
                'race_time': race['race_time']
            })

    # Sort all value bets by score (descending)
    all_value_bets.sort(key=lambda x: x['value_score'], reverse=True)

    return all_value_bets


def get_tracked_value_bets(hours_ahead: int = 4) -> List[Dict[str, Any]]:
    """
    Returns value bets that have been recorded in bet_history.

    Includes their current outcome status (pending/won/lost) and
    actual position if available from race_results.

    Args:
        hours_ahead: Number of hours to look ahead for pending bets (default 4)

    Returns:
        List of tracked bet dictionaries containing:
        - bet_id: Unique bet identifier
        - race_id: Race identifier
        - dog_id: Dog identifier
        - dog_name: Dog name (if available)
        - track_name: Track name
        - race_time: Race time
        - value_score: Value score at time of suggestion
        - best_odds: Best odds when suggested
        - best_bookmaker: Bookmaker offering best odds
        - outcome: 'pending', 'won', or 'lost'
        - actual_position: Finishing position if result available
        - profit_loss: Profit/loss if resolved

    Example:
        tracked = get_tracked_value_bets(hours_ahead=4)
        for bet in tracked:
            print(f"{bet['dog_name']}: {bet['outcome']} (pos: {bet['actual_position']})")
    """
    db = get_db()
    tracked_bets = []

    try:
        # Get recent bet history
        history = get_betting_history(limit=100)

        for bet in history:
            race_id = bet['race_id']

            # Get race info for context
            race = get_race_with_dogs(race_id)
            if not race:
                continue

            # Find the dog name from race dogs
            dog_name = None
            for dog in race.get('dogs', []):
                if dog['dog_id'] == bet['dog_id']:
                    dog_name = dog.get('name')
                    break

            # Get actual position from race_results if not already in bet
            actual_position = bet.get('actual_position')
            if actual_position is None and bet.get('outcome') != 'pending':
                results = get_race_results(race_id)
                for result in results:
                    if result['dog_id'] == bet['dog_id']:
                        actual_position = result['position']
                        break

            tracked_bets.append({
                'bet_id': bet['bet_id'],
                'race_id': race_id,
                'dog_id': bet['dog_id'],
                'dog_name': dog_name or bet['dog_id'],
                'track_name': race.get('track_name', 'Unknown'),
                'race_time': race.get('race_time'),
                'value_score': float(bet['value_score']),
                'best_odds': float(bet['best_odds']),
                'best_bookmaker': bet['best_bookmaker'],
                'outcome': bet['outcome'],
                'actual_position': actual_position,
                'profit_loss': float(bet['profit_loss']) if bet.get('profit_loss') is not None else None,
                'suggested_at': bet['suggested_at']
            })

        # Sort by suggested_at descending (most recent first)
        tracked_bets.sort(key=lambda x: x['suggested_at'] if x['suggested_at'] else datetime.min, reverse=True)

        return tracked_bets

    except Exception as e:
        logger.error(f"Error getting tracked value bets: {e}")
        return []


def update_value_bet_outcomes() -> int:
    """
    Scan all pending bets where race_time has passed and update outcomes.

    Checks race_results table for completed races and updates bet_history
    with actual positions and profit/loss.

    Returns:
        int: Number of bets updated

    Example:
        updated_count = update_value_bet_outcomes()
        print(f"Updated {updated_count} bet outcomes")
    """
    db = get_db()
    total_updated = 0

    try:
        # Get all pending bets
        pending_query = """
            SELECT DISTINCT race_id FROM bet_history
            WHERE outcome = 'pending'
        """
        pending_races = db.execute_query(pending_query, fetch=True)

        if not pending_races:
            logger.info("No pending bets to update")
            return 0

        now = datetime.now()

        for race_row in pending_races:
            race_id = race_row['race_id']

            # Check if race has passed
            race = get_race_with_dogs(race_id)
            if not race:
                continue

            race_time = race.get('race_time')
            if race_time and race_time > now:
                # Race hasn't happened yet, skip
                continue

            # Check if we have results for this race
            results = get_race_results(race_id)
            if not results:
                # No results yet, skip
                continue

            # Update bet outcomes for this race
            updated = update_bet_outcome(race_id)
            total_updated += updated

            if updated > 0:
                logger.info(f"Updated {updated} bet outcomes for race {race_id}")

        return total_updated

    except Exception as e:
        logger.error(f"Error updating value bet outcomes: {e}")
        return total_updated


def find_and_record_all_value_bets(hours_ahead: int = 4) -> Dict[str, Any]:
    """
    Scan all upcoming races, identify value bets, and record them to bet_history.

    Convenience function that combines get_all_value_bets with bet recording.

    Args:
        hours_ahead: Number of hours to look ahead for races (default 4)

    Returns:
        Dict with:
        - value_bets: List of all value bets found
        - new_bets_recorded: Number of new bets recorded to bet_history

    Example:
        result = find_and_record_all_value_bets(hours_ahead=4)
        print(f"Found {len(result['value_bets'])} value bets")
        print(f"Recorded {result['new_bets_recorded']} new bets")
    """
    races = get_upcoming_races(hours_ahead)
    all_value_bets = []
    total_recorded = 0

    for race in races:
        race_id = race['race_id']

        # Find value bets for this race AND record them
        value_bets = find_value_bets_for_race(race_id, record_bets=True)

        # Add race context to each value bet
        for vb in value_bets:
            all_value_bets.append({
                **vb,
                'race_id': race_id,
                'track_name': race['track_name'],
                'race_time': race['race_time']
            })

    # Sort all value bets by score (descending)
    all_value_bets.sort(key=lambda x: x['value_score'], reverse=True)

    return {
        'value_bets': all_value_bets,
        'races_scanned': len(races)
    }

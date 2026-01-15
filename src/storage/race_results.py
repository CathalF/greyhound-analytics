"""
Race Results and Bet History Storage Layer

Provides functions for storing and retrieving race results and betting history.
Supports recording value bets, updating outcomes, and calculating performance stats.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import psycopg2
from src.storage.db import get_db


def insert_race_results(race_id: str, results: List[Dict]) -> int:
    """
    Insert multiple race result records.

    Args:
        race_id: Race ID for these results
        results: List of result dictionaries with keys:
            - dog_id: Dog ID
            - position: Finishing position (1-6)
            - finishing_time: Time in seconds (optional, e.g., "29.45")
            - starting_price: SP odds at race start (optional)

    Returns:
        int: Number of result records successfully inserted

    Example:
        results = [
            {'dog_id': 'rathbally-bolger', 'position': 1, 'finishing_time': '29.45', 'starting_price': 3.5},
            {'dog_id': 'swift-arrow', 'position': 2, 'finishing_time': '29.52', 'starting_price': 4.0},
        ]
        count = insert_race_results('harlow_1811_20260114', results)
        print(f"Inserted {count} results")
    """
    db = get_db()

    if not results:
        return 0

    inserted_count = 0
    now = datetime.now()

    try:
        for result_dict in results:
            dog_id = result_dict.get('dog_id')
            position = result_dict.get('position')
            finishing_time = result_dict.get('finishing_time')
            starting_price = result_dict.get('starting_price')

            if not dog_id or position is None:
                print(f"Warning: Skipping result record with missing fields")
                continue

            # Generate unique result_id
            result_id = f"{race_id}_{position}"

            query = """
                INSERT INTO race_results (result_id, race_id, dog_id, position, finishing_time, starting_price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (result_id)
                DO UPDATE SET
                    dog_id = EXCLUDED.dog_id,
                    finishing_time = EXCLUDED.finishing_time,
                    starting_price = EXCLUDED.starting_price
            """

            params = (
                result_id,
                race_id,
                dog_id,
                position,
                finishing_time,
                starting_price,
                now
            )

            db.execute_query(query, params, fetch=False)
            inserted_count += 1

        return inserted_count

    except psycopg2.Error as e:
        print(f"Error inserting race results (inserted {inserted_count} before error): {e}")
        return inserted_count


def get_race_results(race_id: str) -> List[Dict[str, Any]]:
    """
    Get all results for a race.

    Args:
        race_id: Race ID

    Returns:
        List of result dictionaries ordered by position

    Example:
        results = get_race_results('harlow_1811_20260114')
        for result in results:
            print(f"Position {result['position']}: {result['dog_id']} in {result['finishing_time']}")
    """
    db = get_db()

    try:
        query = """
            SELECT result_id, race_id, dog_id, position, finishing_time, starting_price, created_at
            FROM race_results
            WHERE race_id = %s
            ORDER BY position
        """

        results = db.execute_query(query, (race_id,), fetch=True)

        return [dict(row) for row in results] if results else []

    except psycopg2.Error as e:
        print(f"Error retrieving results for race '{race_id}': {e}")
        return []


def record_value_bet(race_id: str, dog_id: str, value_score: float, best_odds: float, best_bookmaker: str) -> str:
    """
    Record a suggested value bet.

    Args:
        race_id: Race ID
        dog_id: Dog ID
        value_score: Value score at time of suggestion
        best_odds: Best odds when suggested
        best_bookmaker: Bookmaker offering best odds

    Returns:
        str: Generated bet_id

    Example:
        bet_id = record_value_bet(
            'harlow_1811_20260114',
            'rathbally-bolger',
            1.45,
            5.5,
            'Bet365'
        )
        print(f"Recorded bet with ID: {bet_id}")
    """
    db = get_db()
    now = datetime.now()

    # Generate unique bet_id
    timestamp_str = int(now.timestamp())
    bet_id = f"{race_id}_{dog_id}_{timestamp_str}"

    try:
        query = """
            INSERT INTO bet_history (bet_id, race_id, dog_id, suggested_at, value_score, best_odds, best_bookmaker, outcome, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (bet_id) DO NOTHING
        """

        params = (
            bet_id,
            race_id,
            dog_id,
            now,
            value_score,
            best_odds,
            best_bookmaker,
            'pending',
            now
        )

        db.execute_query(query, params, fetch=False)
        return bet_id

    except psycopg2.Error as e:
        print(f"Error recording value bet: {e}")
        return ""


def update_bet_outcome(race_id: str) -> int:
    """
    Update all bet_history records for a race with actual positions and profit/loss.

    Should be called after race results are recorded. Updates outcome based on
    whether the bet dog finished first (won) or not (lost).

    Args:
        race_id: Race ID to update bets for

    Returns:
        int: Number of bet records updated

    Example:
        # After recording race results
        updated = update_bet_outcome('harlow_1811_20260114')
        print(f"Updated {updated} bet records")
    """
    db = get_db()

    try:
        # Get all pending bets for this race
        bets_query = """
            SELECT bet_id, dog_id, best_odds
            FROM bet_history
            WHERE race_id = %s AND outcome = 'pending'
        """
        pending_bets = db.execute_query(bets_query, (race_id,), fetch=True)

        if not pending_bets:
            return 0

        # Get race results
        results_query = """
            SELECT dog_id, position
            FROM race_results
            WHERE race_id = %s
        """
        results = db.execute_query(results_query, (race_id,), fetch=True)

        if not results:
            return 0

        # Create dog_id -> position mapping
        position_map = {row['dog_id']: row['position'] for row in results}

        updated_count = 0
        for bet in pending_bets:
            bet_id = bet['bet_id']
            dog_id = bet['dog_id']
            best_odds = float(bet['best_odds'])

            actual_position = position_map.get(dog_id)
            if actual_position is None:
                # Dog not in results (scratched or error)
                continue

            # Determine outcome and profit/loss
            if actual_position == 1:
                outcome = 'won'
                profit_loss = best_odds - 1  # Net profit on a 1 unit stake
            else:
                outcome = 'lost'
                profit_loss = -1  # Lost the stake

            # Update bet record
            update_query = """
                UPDATE bet_history
                SET outcome = %s, actual_position = %s, profit_loss = %s
                WHERE bet_id = %s
            """
            db.execute_query(update_query, (outcome, actual_position, profit_loss, bet_id), fetch=False)
            updated_count += 1

        return updated_count

    except psycopg2.Error as e:
        print(f"Error updating bet outcomes for race '{race_id}': {e}")
        return 0


def get_betting_history(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent bet history with outcomes.

    Args:
        limit: Maximum number of records to return (default 50)

    Returns:
        List of bet record dictionaries ordered by suggested_at descending

    Example:
        history = get_betting_history(limit=20)
        for bet in history:
            print(f"{bet['race_id']}: {bet['dog_id']} - {bet['outcome']} ({bet['profit_loss']})")
    """
    db = get_db()

    try:
        query = """
            SELECT bet_id, race_id, dog_id, suggested_at, value_score, best_odds, best_bookmaker,
                   outcome, actual_position, profit_loss, created_at
            FROM bet_history
            ORDER BY suggested_at DESC
            LIMIT %s
        """

        results = db.execute_query(query, (limit,), fetch=True)

        return [dict(row) for row in results] if results else []

    except psycopg2.Error as e:
        print(f"Error retrieving betting history: {e}")
        return []


def get_betting_stats() -> Dict[str, Any]:
    """
    Return summary statistics for betting performance.

    Returns:
        Dict with stats:
            - total_bets: Total number of bets recorded
            - pending: Number of pending bets
            - wins: Number of winning bets
            - losses: Number of losing bets
            - win_rate: Percentage of resolved bets that won
            - total_profit: Sum of all profit/loss
            - roi: Return on investment percentage

    Example:
        stats = get_betting_stats()
        print(f"Win rate: {stats['win_rate']:.1f}%")
        print(f"Total profit: {stats['total_profit']:.2f} units")
        print(f"ROI: {stats['roi']:.1f}%")
    """
    db = get_db()

    try:
        # Get counts by outcome
        count_query = """
            SELECT outcome, COUNT(*) as count
            FROM bet_history
            GROUP BY outcome
        """
        counts = db.execute_query(count_query, fetch=True)

        outcome_counts = {row['outcome']: row['count'] for row in counts} if counts else {}

        total_bets = sum(outcome_counts.values())
        pending = outcome_counts.get('pending', 0)
        wins = outcome_counts.get('won', 0)
        losses = outcome_counts.get('lost', 0)

        resolved = wins + losses
        win_rate = (wins / resolved * 100) if resolved > 0 else 0.0

        # Get total profit/loss
        profit_query = """
            SELECT COALESCE(SUM(profit_loss), 0) as total_profit
            FROM bet_history
            WHERE outcome IN ('won', 'lost')
        """
        profit_result = db.execute_query(profit_query, fetch=True)
        total_profit = float(profit_result[0]['total_profit']) if profit_result else 0.0

        # ROI = (profit / total stake) * 100
        # Each bet represents 1 unit stake
        roi = (total_profit / resolved * 100) if resolved > 0 else 0.0

        return {
            'total_bets': total_bets,
            'pending': pending,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'roi': roi
        }

    except psycopg2.Error as e:
        print(f"Error retrieving betting stats: {e}")
        return {
            'total_bets': 0,
            'pending': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_profit': 0.0,
            'roi': 0.0
        }

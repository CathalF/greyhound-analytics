"""
Pattern Analyzer Service

Analyzes historical race data to identify winning patterns and trends.
Provides insights on track performance, value score effectiveness, form correlation,
trap bias, and time-of-day patterns.
"""

from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import logging

from src.storage.db import get_db

# Set up logging
logger = logging.getLogger(__name__)


def get_track_performance() -> Dict[str, Dict]:
    """
    Analyze bet performance grouped by track.

    Queries bet_history joined with races grouped by track name.
    For each track calculates: win_count, loss_count, win_rate, total_profit, roi.

    Returns:
        Dict keyed by track name with performance metrics:
        {
            'Hove': {
                'win_count': 7,
                'loss_count': 8,
                'win_rate': 46.67,
                'total_profit': 2.5,
                'roi': 16.67,
                'sample_size': 15
            },
            ...
        }
    """
    db = get_db()

    try:
        query = """
            SELECT
                r.track_name,
                COUNT(*) as total_bets,
                SUM(CASE WHEN bh.outcome = 'won' THEN 1 ELSE 0 END) as win_count,
                SUM(CASE WHEN bh.outcome = 'lost' THEN 1 ELSE 0 END) as loss_count,
                COALESCE(SUM(bh.profit_loss), 0) as total_profit
            FROM bet_history bh
            JOIN races r ON bh.race_id = r.race_id
            WHERE bh.outcome IN ('won', 'lost')
            GROUP BY r.track_name
            ORDER BY COUNT(*) DESC
        """

        results = db.execute_query(query, fetch=True)

        if not results:
            return {}

        track_performance = {}
        for row in results:
            track_name = row['track_name']
            win_count = row['win_count'] or 0
            loss_count = row['loss_count'] or 0
            sample_size = win_count + loss_count
            total_profit = float(row['total_profit'] or 0)

            win_rate = round((win_count / sample_size * 100), 2) if sample_size > 0 else 0.0
            roi = round((total_profit / sample_size * 100), 2) if sample_size > 0 else 0.0

            track_performance[track_name] = {
                'win_count': win_count,
                'loss_count': loss_count,
                'win_rate': win_rate,
                'total_profit': round(total_profit, 2),
                'roi': roi,
                'sample_size': sample_size
            }

        return track_performance

    except Exception as e:
        logger.error(f"Error getting track performance: {e}")
        return {}


def get_value_score_performance(
    buckets: Optional[List[Tuple[float, float]]] = None
) -> Dict[str, Dict]:
    """
    Analyze bet outcomes by value score ranges.

    Helps identify optimal value threshold by showing performance at different score levels.

    Args:
        buckets: List of (min, max) tuples for value score ranges.
                 Default: [(1.2, 1.3), (1.3, 1.4), (1.4, 1.5), (1.5, 2.0), (2.0, inf)]

    Returns:
        Dict keyed by bucket range string with performance metrics:
        {
            '1.2-1.3': {
                'win_count': 6,
                'loss_count': 14,
                'win_rate': 30.0,
                'avg_odds': 4.2,
                'total_profit': -2.5,
                'roi': -12.5,
                'sample_size': 20
            },
            ...
        }
    """
    if buckets is None:
        buckets = [
            (1.2, 1.3),
            (1.3, 1.4),
            (1.4, 1.5),
            (1.5, 2.0),
            (2.0, float('inf'))
        ]

    db = get_db()

    try:
        # Get all resolved bets with value scores
        query = """
            SELECT value_score, best_odds, outcome, profit_loss
            FROM bet_history
            WHERE outcome IN ('won', 'lost')
        """

        results = db.execute_query(query, fetch=True)

        if not results:
            return {}

        # Initialize bucket stats
        bucket_stats = {}
        for min_val, max_val in buckets:
            if max_val == float('inf'):
                bucket_key = f"{min_val}+"
            else:
                bucket_key = f"{min_val}-{max_val}"
            bucket_stats[bucket_key] = {
                'win_count': 0,
                'loss_count': 0,
                'total_odds': 0.0,
                'total_profit': 0.0,
                'count': 0
            }

        # Categorize each bet into buckets
        for row in results:
            value_score = float(row['value_score'])
            best_odds = float(row['best_odds'])
            outcome = row['outcome']
            profit_loss = float(row['profit_loss'] or 0)

            for min_val, max_val in buckets:
                if min_val <= value_score < max_val:
                    if max_val == float('inf'):
                        bucket_key = f"{min_val}+"
                    else:
                        bucket_key = f"{min_val}-{max_val}"

                    bucket_stats[bucket_key]['count'] += 1
                    bucket_stats[bucket_key]['total_odds'] += best_odds
                    bucket_stats[bucket_key]['total_profit'] += profit_loss

                    if outcome == 'won':
                        bucket_stats[bucket_key]['win_count'] += 1
                    else:
                        bucket_stats[bucket_key]['loss_count'] += 1
                    break

        # Calculate final metrics for each bucket
        value_performance = {}
        for bucket_key, stats in bucket_stats.items():
            sample_size = stats['count']
            if sample_size == 0:
                continue

            win_count = stats['win_count']
            loss_count = stats['loss_count']
            win_rate = round((win_count / sample_size * 100), 2)
            avg_odds = round(stats['total_odds'] / sample_size, 2)
            total_profit = round(stats['total_profit'], 2)
            roi = round((total_profit / sample_size * 100), 2)

            value_performance[bucket_key] = {
                'win_count': win_count,
                'loss_count': loss_count,
                'win_rate': win_rate,
                'avg_odds': avg_odds,
                'total_profit': total_profit,
                'roi': roi,
                'sample_size': sample_size
            }

        return value_performance

    except Exception as e:
        logger.error(f"Error getting value score performance: {e}")
        return {}


def get_form_correlation() -> Dict[str, Dict]:
    """
    Analyze correlation between recent form and bet outcomes.

    Groups dogs by their recent form pattern (e.g., dogs with 3+ wins in last 5 races)
    and calculates performance for each category.

    Returns:
        Dict keyed by form category with metrics:
        {
            'strong_form': {  # 3+ wins in last 5
                'win_rate': 52.5,
                'sample_size': 20,
                'avg_value_score': 1.35
            },
            'moderate_form': {  # 1-2 wins in last 5
                'win_rate': 38.0,
                'sample_size': 25,
                'avg_value_score': 1.42
            },
            'weak_form': {  # 0 wins in last 5
                'win_rate': 22.0,
                'sample_size': 10,
                'avg_value_score': 1.55
            }
        }
    """
    db = get_db()

    try:
        # Get bets with dog stats (which contain recent_form)
        query = """
            SELECT bh.outcome, bh.value_score, d.stats
            FROM bet_history bh
            JOIN dogs d ON bh.dog_id = d.dog_id
            WHERE bh.outcome IN ('won', 'lost')
              AND d.stats IS NOT NULL
        """

        results = db.execute_query(query, fetch=True)

        if not results:
            return {}

        # Initialize form categories
        form_stats = {
            'strong_form': {'wins': 0, 'total': 0, 'value_scores': []},
            'moderate_form': {'wins': 0, 'total': 0, 'value_scores': []},
            'weak_form': {'wins': 0, 'total': 0, 'value_scores': []},
            'unknown_form': {'wins': 0, 'total': 0, 'value_scores': []}
        }

        for row in results:
            outcome = row['outcome']
            value_score = float(row['value_score'])
            stats = row['stats'] or {}

            # Get recent form and count recent wins
            recent_form = stats.get('recent_form', [])
            if recent_form and isinstance(recent_form, list):
                # Count wins (position 1) in last 5 races
                recent_positions = [r.get('position', 0) for r in recent_form[:5] if isinstance(r, dict)]
                recent_wins = sum(1 for pos in recent_positions if pos == 1)

                if recent_wins >= 3:
                    category = 'strong_form'
                elif recent_wins >= 1:
                    category = 'moderate_form'
                else:
                    category = 'weak_form'
            else:
                category = 'unknown_form'

            form_stats[category]['total'] += 1
            form_stats[category]['value_scores'].append(value_score)
            if outcome == 'won':
                form_stats[category]['wins'] += 1

        # Calculate final metrics
        form_correlation = {}
        for category, stats in form_stats.items():
            sample_size = stats['total']
            if sample_size == 0:
                continue

            win_rate = round((stats['wins'] / sample_size * 100), 2)
            avg_value_score = round(sum(stats['value_scores']) / sample_size, 2)

            form_correlation[category] = {
                'win_rate': win_rate,
                'sample_size': sample_size,
                'avg_value_score': avg_value_score
            }

        return form_correlation

    except Exception as e:
        logger.error(f"Error getting form correlation: {e}")
        return {}


def get_trap_bias() -> Dict[int, Dict]:
    """
    Analyze win rates by trap number (1-6).

    From race_results, counts wins by trap position across all races.
    Identifies if certain traps have statistical advantages.

    Returns:
        Dict keyed by trap number with win statistics:
        {
            1: {'wins': 15, 'total_races': 95, 'win_rate': 15.79},
            2: {'wins': 17, 'total_races': 95, 'win_rate': 17.89},
            ...
        }
    """
    db = get_db()

    try:
        # Get win counts by trap position
        query = """
            SELECT
                d.trap_number,
                COUNT(*) as total_entries,
                SUM(CASE WHEN rr.position = 1 THEN 1 ELSE 0 END) as wins
            FROM race_results rr
            JOIN dogs d ON rr.dog_id = d.dog_id AND d.race_id = rr.race_id
            WHERE d.trap_number IS NOT NULL
            GROUP BY d.trap_number
            ORDER BY d.trap_number
        """

        results = db.execute_query(query, fetch=True)

        if not results:
            # Return empty structure for all traps
            return {i: {'wins': 0, 'total_races': 0, 'win_rate': 0.0} for i in range(1, 7)}

        trap_bias = {}
        for row in results:
            trap_num = row['trap_number']
            wins = row['wins'] or 0
            total = row['total_entries'] or 0
            win_rate = round((wins / total * 100), 2) if total > 0 else 0.0

            trap_bias[trap_num] = {
                'wins': wins,
                'total_races': total,
                'win_rate': win_rate
            }

        # Fill in missing traps with zeros
        for i in range(1, 7):
            if i not in trap_bias:
                trap_bias[i] = {'wins': 0, 'total_races': 0, 'win_rate': 0.0}

        return trap_bias

    except Exception as e:
        logger.error(f"Error getting trap bias: {e}")
        return {i: {'wins': 0, 'total_races': 0, 'win_rate': 0.0} for i in range(1, 7)}


def get_time_of_day_analysis() -> Dict[str, Dict]:
    """
    Analyze bet performance by time of day.

    Groups races by time slot:
    - morning: before 14:00
    - afternoon: 14:00-18:00
    - evening: after 18:00

    Returns:
        Dict keyed by time slot with performance metrics:
        {
            'morning': {
                'win_count': 5,
                'loss_count': 10,
                'win_rate': 33.33,
                'total_profit': -2.0,
                'roi': -13.33,
                'sample_size': 15
            },
            ...
        }
    """
    db = get_db()

    try:
        query = """
            SELECT
                EXTRACT(HOUR FROM r.race_time) as race_hour,
                bh.outcome,
                bh.profit_loss
            FROM bet_history bh
            JOIN races r ON bh.race_id = r.race_id
            WHERE bh.outcome IN ('won', 'lost')
        """

        results = db.execute_query(query, fetch=True)

        if not results:
            return {}

        # Initialize time slots
        time_stats = {
            'morning': {'wins': 0, 'losses': 0, 'profit': 0.0},
            'afternoon': {'wins': 0, 'losses': 0, 'profit': 0.0},
            'evening': {'wins': 0, 'losses': 0, 'profit': 0.0}
        }

        for row in results:
            hour = int(row['race_hour'])
            outcome = row['outcome']
            profit_loss = float(row['profit_loss'] or 0)

            # Categorize by time slot
            if hour < 14:
                slot = 'morning'
            elif hour < 18:
                slot = 'afternoon'
            else:
                slot = 'evening'

            time_stats[slot]['profit'] += profit_loss
            if outcome == 'won':
                time_stats[slot]['wins'] += 1
            else:
                time_stats[slot]['losses'] += 1

        # Calculate final metrics
        time_analysis = {}
        for slot, stats in time_stats.items():
            sample_size = stats['wins'] + stats['losses']
            if sample_size == 0:
                continue

            win_rate = round((stats['wins'] / sample_size * 100), 2)
            total_profit = round(stats['profit'], 2)
            roi = round((total_profit / sample_size * 100), 2)

            time_analysis[slot] = {
                'win_count': stats['wins'],
                'loss_count': stats['losses'],
                'win_rate': win_rate,
                'total_profit': total_profit,
                'roi': roi,
                'sample_size': sample_size
            }

        return time_analysis

    except Exception as e:
        logger.error(f"Error getting time of day analysis: {e}")
        return {}


def get_betting_summary() -> Dict[str, Any]:
    """
    Get comprehensive betting performance summary.

    Aggregates overall stats and identifies best/worst performers.

    Returns:
        Dict with summary statistics:
        {
            'total_bets': 45,
            'wins': 18,
            'losses': 27,
            'pending': 5,
            'win_rate': 40.0,
            'total_profit': 5.5,
            'roi': 12.22,
            'best_track': {'name': 'Hove', 'roi': 25.5},
            'worst_track': {'name': 'Harlow', 'roi': -15.2},
            'best_value_bucket': {'range': '1.3-1.4', 'roi': 18.0},
            'current_streak': {'type': 'win', 'count': 3}
        }
    """
    db = get_db()

    try:
        # Get basic counts
        count_query = """
            SELECT
                COUNT(*) as total_bets,
                SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(CASE WHEN outcome IN ('won', 'lost') THEN profit_loss ELSE 0 END), 0) as total_profit
            FROM bet_history
        """

        count_result = db.execute_query(count_query, fetch=True)

        if not count_result:
            return _empty_summary()

        row = count_result[0]
        total_bets = row['total_bets'] or 0
        wins = row['wins'] or 0
        losses = row['losses'] or 0
        pending = row['pending'] or 0
        total_profit = float(row['total_profit'] or 0)

        resolved = wins + losses
        win_rate = round((wins / resolved * 100), 2) if resolved > 0 else 0.0
        roi = round((total_profit / resolved * 100), 2) if resolved > 0 else 0.0

        # Get best/worst track
        track_perf = get_track_performance()
        best_track = {'name': 'N/A', 'roi': 0.0}
        worst_track = {'name': 'N/A', 'roi': 0.0}

        if track_perf:
            tracks_by_roi = sorted(track_perf.items(), key=lambda x: x[1]['roi'], reverse=True)
            if tracks_by_roi:
                best_track = {'name': tracks_by_roi[0][0], 'roi': tracks_by_roi[0][1]['roi']}
                worst_track = {'name': tracks_by_roi[-1][0], 'roi': tracks_by_roi[-1][1]['roi']}

        # Get best value bucket
        value_perf = get_value_score_performance()
        best_value_bucket = {'range': 'N/A', 'roi': 0.0}

        if value_perf:
            buckets_by_roi = sorted(value_perf.items(), key=lambda x: x[1]['roi'], reverse=True)
            if buckets_by_roi:
                best_value_bucket = {'range': buckets_by_roi[0][0], 'roi': buckets_by_roi[0][1]['roi']}

        # Get current streak
        streak_query = """
            SELECT outcome
            FROM bet_history
            WHERE outcome IN ('won', 'lost')
            ORDER BY suggested_at DESC
            LIMIT 20
        """
        streak_result = db.execute_query(streak_query, fetch=True)

        current_streak = {'type': 'none', 'count': 0}
        if streak_result:
            first_outcome = streak_result[0]['outcome']
            streak_count = 0
            for row in streak_result:
                if row['outcome'] == first_outcome:
                    streak_count += 1
                else:
                    break
            current_streak = {'type': first_outcome, 'count': streak_count}

        return {
            'total_bets': total_bets,
            'wins': wins,
            'losses': losses,
            'pending': pending,
            'win_rate': win_rate,
            'total_profit': round(total_profit, 2),
            'roi': roi,
            'best_track': best_track,
            'worst_track': worst_track,
            'best_value_bucket': best_value_bucket,
            'current_streak': current_streak
        }

    except Exception as e:
        logger.error(f"Error getting betting summary: {e}")
        return _empty_summary()


def _empty_summary() -> Dict[str, Any]:
    """Return empty summary structure for when no data exists."""
    return {
        'total_bets': 0,
        'wins': 0,
        'losses': 0,
        'pending': 0,
        'win_rate': 0.0,
        'total_profit': 0.0,
        'roi': 0.0,
        'best_track': {'name': 'N/A', 'roi': 0.0},
        'worst_track': {'name': 'N/A', 'roi': 0.0},
        'best_value_bucket': {'range': 'N/A', 'roi': 0.0},
        'current_streak': {'type': 'none', 'count': 0}
    }

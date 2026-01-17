"""
API Routes

JSON endpoints for AJAX updates and future mobile app integration.
Includes advanced value data with multi-factor scoring breakdowns.
"""

from flask import Blueprint, jsonify
from datetime import datetime
from src.storage.race_odds import get_upcoming_races, get_race_with_dogs, get_race_odds
from src.services.value_finder import find_value_bets_for_race, get_all_value_bets, BOOKMAKER_NAMES
from src.services.pattern_analyzer import get_betting_summary

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/races')
def races():
    """
    Get list of upcoming races (JSON).

    Returns:
        JSON array of race objects with basic info
    """
    races = get_upcoming_races(hours_ahead=4)

    # Convert datetime objects to ISO format strings
    for race in races:
        if 'race_time' in race:
            race['race_time'] = race['race_time'].isoformat()
        if 'created_at' in race:
            race['created_at'] = race['created_at'].isoformat()
        if 'updated_at' in race:
            race['updated_at'] = race['updated_at'].isoformat()

    return jsonify(races)


@bp.route('/race/<race_id>')
def race_detail(race_id):
    """
    Get detailed race information including dogs and odds (JSON).

    Returns:
        JSON object with race, dogs, and odds data
    """
    race = get_race_with_dogs(race_id)

    if not race:
        return jsonify({'error': 'Race not found'}), 404

    odds = get_race_odds(race_id)

    # Convert datetime objects to ISO format strings
    if 'race_time' in race:
        race['race_time'] = race['race_time'].isoformat()
    if 'created_at' in race:
        race['created_at'] = race['created_at'].isoformat()
    if 'updated_at' in race:
        race['updated_at'] = race['updated_at'].isoformat()

    for dog in race.get('dogs', []):
        if 'created_at' in dog:
            dog['created_at'] = dog['created_at'].isoformat()

    for odd in odds:
        if 'timestamp' in odd:
            odd['timestamp'] = odd['timestamp'].isoformat()
        if 'created_at' in odd:
            odd['created_at'] = odd['created_at'].isoformat()

    return jsonify({
        'race': race,
        'odds': odds
    })


@bp.route('/value-bets')
def value_bets():
    """
    Get all identified value bets across upcoming races (JSON).

    Returns:
        JSON array of value bet objects with race and dog info
    """
    value_bets = get_all_value_bets(hours_ahead=4)

    return jsonify(value_bets)


@bp.route('/race/<race_id>/value')
def race_value(race_id):
    """
    Get advanced value analysis for a specific race.

    Returns detailed value bet data with factor breakdowns for each dog
    identified as a value bet.

    Returns:
        JSON object with race info and value_bets array containing:
        - dog_id, dog_name, trap_number
        - basic_score, advanced_score, confidence
        - best_odds, best_bookmaker
        - factor_breakdown with contributions for each factor
    """
    # Get race info
    race = get_race_with_dogs(race_id)

    if not race:
        return jsonify({'error': 'Race not found'}), 404

    # Get value bets with advanced scoring
    value_bets_data = find_value_bets_for_race(race_id, use_advanced=True)

    # Convert datetime to ISO format
    race_time = race.get('race_time')
    if race_time and hasattr(race_time, 'isoformat'):
        race_time = race_time.isoformat()

    # Format response
    response = {
        'race_id': race_id,
        'track_name': race.get('track_name', ''),
        'race_time': race_time,
        'value_bets': [
            {
                'dog_id': vb['dog_id'],
                'dog_name': vb['dog_name'],
                'trap_number': vb['trap_number'],
                'basic_score': vb['value_score'],
                'advanced_score': vb.get('advanced_score'),
                'confidence': vb.get('confidence'),
                'best_odds': float(vb['best_odds']),
                'best_bookmaker': vb.get('best_bookmaker', ''),
                'factor_breakdown': _format_factor_breakdown(vb.get('factor_breakdown', {}))
            }
            for vb in value_bets_data
        ],
        'generated_at': datetime.now().isoformat()
    }

    return jsonify(response)


@bp.route('/value/summary')
def value_summary():
    """
    Get overall value betting performance summary.

    Returns comprehensive betting statistics including ROI, win rate,
    best/worst performing tracks, and current streak.

    Returns:
        JSON object with:
        - total_bets, wins, losses, pending
        - win_rate, roi, total_profit
        - best_track, worst_track
        - best_value_bucket
        - current_streak
    """
    summary = get_betting_summary()

    return jsonify(summary)


def _format_factor_breakdown(factor_breakdown):
    """
    Format factor breakdown for JSON response.

    Calculates total contribution and formats each factor with
    weight, value, contribution, and descriptive note.
    """
    if not factor_breakdown:
        return {}

    formatted = {}
    total_contribution = sum(
        f.get('contribution', 0) for f in factor_breakdown.values()
    )

    for factor_name, factor_data in factor_breakdown.items():
        formatted[factor_name] = {
            'weight': factor_data.get('weight', 0),
            'value': round(factor_data.get('factor', 1.0), 2),
            'contribution': round(factor_data.get('contribution', 0), 3),
            'note': factor_data.get('description', '')
        }

    return formatted

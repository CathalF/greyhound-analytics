"""
Dashboard Routes

Main dashboard displaying upcoming races with value bet opportunities.
Includes advanced multi-factor scoring with confidence indicators.
"""

from flask import Blueprint, render_template
from src.storage.race_odds import get_upcoming_races, get_race_with_dogs
from src.services.value_finder import find_value_bets_for_race, get_all_value_bets
from datetime import datetime

bp = Blueprint('dashboard', __name__)


@bp.route('/')
@bp.route('/dashboard')
def index():
    """
    Main dashboard page showing upcoming races.

    Displays races for the next 4 hours with:
    - Race information (track, time, distance)
    - Number of dogs with stats
    - Value bet indicators
    - Race status badges
    """
    # Get upcoming races (next 4 hours)
    races = get_upcoming_races(hours_ahead=4)

    # Get all value bets with advanced scoring
    all_value_bets = get_all_value_bets(hours_ahead=4, use_advanced=True)

    # Group value bets by race_id for easy lookup
    value_bets_by_race = {}
    for vb in all_value_bets:
        race_id = vb.get('race_id')
        if race_id not in value_bets_by_race:
            value_bets_by_race[race_id] = []
        # Add primary factor for display
        vb['primary_factor'] = _get_primary_factor(vb.get('factor_breakdown', {}))
        value_bets_by_race[race_id].append(vb)

    # Enhance each race with value bet info
    enhanced_races = []
    for race in races:
        # Calculate time until race
        race_time = race['race_time']
        if isinstance(race_time, str):
            race_time = datetime.fromisoformat(race_time.replace('Z', '+00:00'))

        time_until = race_time - datetime.now()
        minutes_until = int(time_until.total_seconds() / 60)

        race_id = race['race_id']
        race_value_bets = value_bets_by_race.get(race_id, [])

        enhanced_races.append({
            **race,
            'total_dogs': 0,  # Will be populated via AJAX if needed
            'dogs_with_stats': 0,
            'value_bet_count': len(race_value_bets),
            'has_value_bets': len(race_value_bets) > 0,
            'value_bets': race_value_bets,
            'minutes_until': minutes_until,
            'formatted_time': race_time.strftime('%H:%M')
        })

    # Sort by time (soonest first)
    enhanced_races.sort(key=lambda r: r['race_time'])

    return render_template('dashboard.html',
                         races=enhanced_races,
                         top_value_bets=all_value_bets[:5],  # Top 5 for summary
                         current_time=datetime.now())


def _get_primary_factor(factor_breakdown):
    """
    Extract the primary contributing factor (excluding base value).

    Identifies which factor (track, form, trap, time) has the most
    significant impact on the score (furthest from 1.0).

    Args:
        factor_breakdown: Dict of factor contributions

    Returns:
        str: Human-readable description of primary factor (e.g., "Track +15%")
    """
    if not factor_breakdown:
        return ""

    # Find highest impact factor (excluding base_value)
    highest_impact = None
    highest_deviation = 0

    for factor_name, factor_data in factor_breakdown.items():
        if factor_name == 'base_value':
            continue

        factor_value = factor_data.get('factor', 1.0)
        deviation = abs(factor_value - 1.0)

        if deviation > highest_deviation:
            highest_deviation = deviation
            highest_impact = (factor_name, factor_value, factor_data.get('description', ''))

    if not highest_impact:
        return ""

    name, value, description = highest_impact

    # Format factor name for display
    display_names = {
        'track_factor': 'Track',
        'form_factor': 'Form',
        'trap_factor': 'Trap',
        'time_factor': 'Time'
    }

    display_name = display_names.get(name, name.replace('_', ' ').title())
    diff_pct = (value - 1) * 100
    sign = '+' if diff_pct >= 0 else ''

    return f"{display_name} {sign}{diff_pct:.0f}%"

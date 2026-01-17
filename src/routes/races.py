"""
Race Detail Routes

Individual race pages showing dogs, stats, odds comparison, and value indicators.
Includes advanced multi-factor value scoring with visual breakdowns.
"""

from flask import Blueprint, render_template, abort
from src.storage.race_odds import get_race_with_dogs, get_race_odds
from src.services.value_finder import calculate_value_score, BOOKMAKER_NAMES, TOP_BOOKMAKERS
from src.services.advanced_value import calculate_advanced_value_score
from collections import defaultdict
from datetime import datetime

bp = Blueprint('races', __name__, url_prefix='/race')


@bp.route('/<race_id>')
def detail(race_id):
    """
    Race detail page showing complete information.

    Displays:
    - Race header (track, time, distance, countdown)
    - Table of 6 dogs with trap colors, stats, and odds
    - Odds comparison across top 5 bookmakers
    - Value indicators and scores
    """
    # Get race with dogs
    race = get_race_with_dogs(race_id)

    if not race:
        abort(404, description="Race not found")

    # Get all odds for this race
    all_odds = get_race_odds(race_id)

    # Group odds by dog_id
    odds_by_dog = defaultdict(list)
    for odd in all_odds:
        odds_by_dog[odd['dog_id']].append(odd)

    # Process each dog
    enhanced_dogs = []
    for dog in race['dogs']:
        dog_id = dog['dog_id']
        stats = dog.get('stats', {})

        # Get odds for this dog (filter to top bookmakers)
        dog_odds = [odd for odd in odds_by_dog.get(dog_id, []) if odd['bookmaker'] in TOP_BOOKMAKERS]

        # Find best and worst odds
        if dog_odds:
            best_odds = max(dog_odds, key=lambda x: x['decimal_odds'])
            worst_odds = min(dog_odds, key=lambda x: x['decimal_odds'])

            # Calculate value score if we have stats
            if stats and 'win_rate' in stats:
                value_score, explanation = calculate_value_score(stats, best_odds['decimal_odds'])

                # Calculate advanced score with factor breakdown
                advanced_result = calculate_advanced_value_score(
                    dog_stats=stats,
                    best_decimal_odds=float(best_odds['decimal_odds']),
                    track_name=race.get('track_name', ''),
                    trap_number=dog.get('trap_number', 1),
                    race_time=race.get('race_time')
                )
                advanced_score = advanced_result.get('total_score', 0)
                factor_breakdown = advanced_result.get('factor_breakdown', {})
                confidence = advanced_result.get('confidence', 'low')
                advanced_explanation = advanced_result.get('explanation', explanation)
            else:
                value_score = 0.0
                explanation = "No stats available"
                advanced_score = 0.0
                factor_breakdown = {}
                confidence = 'low'
                advanced_explanation = "No stats available"

            # Organize odds by bookmaker for display
            odds_by_bookmaker = {odd['bookmaker']: odd for odd in dog_odds}

        else:
            best_odds = None
            worst_odds = None
            value_score = 0.0
            explanation = "No odds available"
            advanced_score = 0.0
            factor_breakdown = {}
            confidence = 'low'
            advanced_explanation = "No odds available"
            odds_by_bookmaker = {}

        # Determine value class for styling (based on advanced score)
        if advanced_score >= 1.5:
            value_class = "strong-value"  # Green
        elif advanced_score >= 1.25:
            value_class = "decent-value"  # Yellow
        else:
            value_class = "no-value"  # Red/default

        # Calculate total contribution for progress bar percentages
        total_contribution = sum(
            f.get('contribution', 0) for f in factor_breakdown.values()
        ) if factor_breakdown else 1

        enhanced_dogs.append({
            **dog,
            'best_odds': best_odds,
            'worst_odds': worst_odds,
            'value_score': value_score,
            'advanced_score': advanced_score,
            'factor_breakdown': factor_breakdown,
            'total_contribution': total_contribution,
            'confidence': confidence,
            'value_explanation': advanced_explanation,
            'value_class': value_class,
            'odds_by_bookmaker': odds_by_bookmaker
        })

    # Calculate time until race
    race_time = race['race_time']
    if isinstance(race_time, str):
        race_time = datetime.fromisoformat(race_time.replace('Z', '+00:00'))

    time_until = race_time - datetime.now()
    minutes_until = int(time_until.total_seconds() / 60)

    return render_template('race_detail.html',
                         race=race,
                         dogs=enhanced_dogs,
                         bookmakers=TOP_BOOKMAKERS,
                         bookmaker_names=BOOKMAKER_NAMES,
                         minutes_until=minutes_until,
                         current_time=datetime.now())

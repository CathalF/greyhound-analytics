"""
Advanced Value Calculator Service

Enhanced value scoring algorithm with multi-factor weighting.
Incorporates track performance, form trends, trap bias, and time-of-day patterns
beyond simple win_rate vs implied_probability calculation.

Weights:
    - Base Value: 40% (win_rate / implied_probability)
    - Track Factor: 20% (track-specific win rate ratio)
    - Form Factor: 20% (recent form analysis)
    - Trap Factor: 10% (from pattern_analyzer.get_trap_bias())
    - Time Factor: 10% (from pattern_analyzer.get_time_of_day_analysis())
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from src.services.pattern_analyzer import get_trap_bias, get_time_of_day_analysis

# Set up logging
logger = logging.getLogger(__name__)


# Weighting factors
DEFAULT_WEIGHTS = {
    'base_value': 0.40,
    'track_factor': 0.20,
    'form_factor': 0.20,
    'trap_factor': 0.10,
    'time_factor': 0.10
}

# Cache for pattern data (refreshed every 30 minutes)
_cache = {
    'trap_bias': None,
    'trap_bias_timestamp': None,
    'time_analysis': None,
    'time_analysis_timestamp': None
}
CACHE_TTL_MINUTES = 30


def get_weighting_factors() -> Dict[str, float]:
    """
    Return current factor weights as dict.

    Allows future tuning without code changes.

    Returns:
        Dict with factor names and their weights (sum to 1.0)
    """
    return DEFAULT_WEIGHTS.copy()


def _get_cached_trap_bias() -> Dict[int, Dict]:
    """Get trap bias data with caching (30 minute TTL)."""
    now = datetime.now()

    if (_cache['trap_bias'] is not None and
        _cache['trap_bias_timestamp'] is not None and
        (now - _cache['trap_bias_timestamp']) < timedelta(minutes=CACHE_TTL_MINUTES)):
        return _cache['trap_bias']

    # Refresh cache
    _cache['trap_bias'] = get_trap_bias()
    _cache['trap_bias_timestamp'] = now
    return _cache['trap_bias']


def _get_cached_time_analysis() -> Dict[str, Dict]:
    """Get time of day analysis with caching (30 minute TTL)."""
    now = datetime.now()

    if (_cache['time_analysis'] is not None and
        _cache['time_analysis_timestamp'] is not None and
        (now - _cache['time_analysis_timestamp']) < timedelta(minutes=CACHE_TTL_MINUTES)):
        return _cache['time_analysis']

    # Refresh cache
    _cache['time_analysis'] = get_time_of_day_analysis()
    _cache['time_analysis_timestamp'] = now
    return _cache['time_analysis']


def _calculate_base_score(win_rate_pct: float, implied_probability: float) -> float:
    """
    Calculate base value score: win_rate / implied_probability.

    Args:
        win_rate_pct: Dog's win rate as percentage (e.g., 30.0 for 30%)
        implied_probability: Probability implied by odds (0-1)

    Returns:
        Base score ratio (>1 = value, <1 = poor value)
    """
    if win_rate_pct <= 0 or implied_probability <= 0:
        return 0.0

    win_rate = win_rate_pct / 100.0
    return win_rate / implied_probability


def _calculate_track_factor(dog_stats: Dict[str, Any], track_name: str) -> tuple[float, bool]:
    """
    Calculate track-specific performance factor.

    Compares dog's win rate at this track vs overall win rate.

    Args:
        dog_stats: Dog statistics including track_stats
        track_name: Current race track name

    Returns:
        Tuple of (factor, has_data):
        - factor: Multiplier (e.g., 1.2 if 20% better at this track)
        - has_data: Whether track-specific data was available
    """
    track_stats = dog_stats.get('track_stats', {})
    overall_win_rate = dog_stats.get('win_rate', 0)

    if not track_stats or not overall_win_rate or overall_win_rate <= 0:
        return 1.0, False

    # Look for track-specific data (track names might have different formats)
    track_win_rate = None
    for track_key, stats in track_stats.items():
        if track_name.lower() in track_key.lower() or track_key.lower() in track_name.lower():
            if isinstance(stats, dict):
                track_win_rate = stats.get('win_rate')
            elif isinstance(stats, (int, float)):
                track_win_rate = stats
            break

    if track_win_rate is None or track_win_rate <= 0:
        return 1.0, False

    # Calculate ratio: track_win_rate / overall_win_rate
    factor = track_win_rate / overall_win_rate

    # Cap factor to reasonable bounds (0.5 to 2.0)
    factor = max(0.5, min(2.0, factor))

    return factor, True


def _calculate_form_factor(dog_stats: Dict[str, Any]) -> tuple[float, bool]:
    """
    Calculate form factor based on recent race positions.

    Analyzes last 5 races:
    - Strong form (3+ wins): factor = 1.15
    - Moderate form (1-2 wins): factor = 1.0
    - Weak form (0 wins): factor = 0.85

    Also detects improving form trend.

    Args:
        dog_stats: Dog statistics including recent_form

    Returns:
        Tuple of (factor, has_data):
        - factor: Multiplier based on recent form
        - has_data: Whether form data was available
    """
    recent_form = dog_stats.get('recent_form', [])

    if not recent_form or not isinstance(recent_form, list):
        return 1.0, False

    # Get positions from last 5 races
    positions = []
    for race in recent_form[:5]:
        if isinstance(race, dict):
            pos = race.get('position') or race.get('pos')
            if pos is not None:
                try:
                    positions.append(int(pos))
                except (ValueError, TypeError):
                    pass
        elif isinstance(race, (int, float)):
            positions.append(int(race))

    if not positions:
        return 1.0, False

    # Count wins (position 1)
    wins = sum(1 for pos in positions if pos == 1)

    # Determine form factor
    if wins >= 3:
        factor = 1.15  # Strong form
    elif wins >= 1:
        factor = 1.0   # Moderate form
    else:
        factor = 0.85  # Weak form

    # Detect improving form (recent positions better than earlier)
    if len(positions) >= 3:
        recent_avg = sum(positions[:2]) / 2  # Last 2 races
        earlier_avg = sum(positions[2:]) / len(positions[2:])  # Earlier races

        if recent_avg < earlier_avg - 0.5:
            # Improving form - boost slightly
            factor *= 1.05
        elif recent_avg > earlier_avg + 0.5:
            # Declining form - reduce slightly
            factor *= 0.95

    return factor, True


def _calculate_trap_factor(trap_number: int) -> tuple[float, bool, int]:
    """
    Calculate trap bias factor.

    Compares trap's historical win rate to expected (16.67% = 1/6).

    Args:
        trap_number: Trap number (1-6)

    Returns:
        Tuple of (factor, has_data, sample_size):
        - factor: Multiplier based on trap historical performance
        - has_data: Whether trap data was available
        - sample_size: Number of samples in trap data
    """
    expected_win_rate = 100.0 / 6  # 16.67%

    trap_bias = _get_cached_trap_bias()

    if not trap_bias or trap_number not in trap_bias:
        return 1.0, False, 0

    trap_data = trap_bias[trap_number]
    trap_win_rate = trap_data.get('win_rate', 0)
    sample_size = trap_data.get('total_races', 0)

    if trap_win_rate <= 0 or sample_size < 10:
        return 1.0, False, sample_size

    # Calculate factor: actual_win_rate / expected_win_rate
    factor = trap_win_rate / expected_win_rate

    # Cap factor to reasonable bounds (0.7 to 1.5)
    factor = max(0.7, min(1.5, factor))

    return factor, True, sample_size


def _calculate_time_factor(race_time: Optional[datetime]) -> tuple[float, bool]:
    """
    Calculate time of day factor.

    Determines time slot and uses historical ROI to adjust factor.

    Args:
        race_time: Race time (datetime) or None

    Returns:
        Tuple of (factor, has_data):
        - factor: Multiplier based on time slot performance
        - has_data: Whether time analysis data was available
    """
    if race_time is None:
        return 1.0, False

    # Determine time slot
    hour = race_time.hour
    if hour < 14:
        slot = 'morning'
    elif hour < 18:
        slot = 'afternoon'
    else:
        slot = 'evening'

    time_analysis = _get_cached_time_analysis()

    if not time_analysis or slot not in time_analysis:
        return 1.0, False

    slot_data = time_analysis[slot]
    roi = slot_data.get('roi', 0)
    sample_size = slot_data.get('sample_size', 0)

    if sample_size < 10:
        return 1.0, False

    # Calculate all slots average ROI
    total_roi = 0
    total_slots = 0
    for s, data in time_analysis.items():
        if data.get('sample_size', 0) >= 10:
            total_roi += data.get('roi', 0)
            total_slots += 1

    avg_roi = total_roi / total_slots if total_slots > 0 else 0

    # Factor based on how this slot's ROI compares to average
    # +10% ROI above average = factor of 1.10
    roi_diff = roi - avg_roi
    factor = 1.0 + (roi_diff / 100.0)  # Convert ROI% to multiplier

    # Cap factor to reasonable bounds (0.85 to 1.15)
    factor = max(0.85, min(1.15, factor))

    return factor, True


def _determine_confidence(
    track_has_data: bool,
    form_has_data: bool,
    trap_has_data: bool,
    time_has_data: bool,
    trap_sample_size: int
) -> str:
    """
    Determine confidence level based on data availability.

    Args:
        track_has_data: Whether track-specific data was available
        form_has_data: Whether form data was available
        trap_has_data: Whether trap bias data was available
        time_has_data: Whether time analysis data was available
        trap_sample_size: Number of samples in trap data

    Returns:
        'high', 'medium', or 'low'
    """
    factors_with_data = sum([
        track_has_data,
        form_has_data,
        trap_has_data and trap_sample_size >= 50,
        time_has_data
    ])

    if factors_with_data >= 3:
        return 'high'
    elif factors_with_data >= 2:
        return 'medium'
    else:
        return 'low'


def calculate_advanced_value_score(
    dog_stats: Dict[str, Any],
    best_decimal_odds: float,
    track_name: str,
    trap_number: int,
    race_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Calculate advanced value score with multi-factor weighting.

    Combines 5 factors:
    1. Base Value (40%): win_rate / implied_probability
    2. Track Factor (20%): track-specific win rate ratio
    3. Form Factor (20%): recent form analysis
    4. Trap Factor (10%): historical trap win rates
    5. Time Factor (10%): time-of-day ROI patterns

    Args:
        dog_stats: Dict from dogs table (includes track_stats, distance_stats, recent_form)
        best_decimal_odds: Best decimal odds available across bookmakers
        track_name: Current race track name
        trap_number: Current trap assignment (1-6)
        race_time: Race datetime (for time-of-day factor)

    Returns:
        Dict containing:
        - total_score: float (weighted composite score)
        - base_score: float (original win_rate / implied_probability)
        - factor_breakdown: Dict of each factor's contribution
        - confidence: str ('high', 'medium', 'low')
        - explanation: str (human-readable summary)

    Example:
        result = calculate_advanced_value_score(
            dog_stats={'win_rate': 30, 'track_stats': {}, 'recent_form': []},
            best_decimal_odds=4.0,
            track_name='Hove',
            trap_number=1,
            race_time=datetime(2026, 1, 17, 19, 30)
        )
        print(f"Score: {result['total_score']}, Confidence: {result['confidence']}")
    """
    weights = get_weighting_factors()

    # Get win rate and implied probability
    win_rate_pct = dog_stats.get('win_rate', 0)

    if win_rate_pct <= 0 or best_decimal_odds <= 1.0:
        return {
            'total_score': 0.0,
            'base_score': 0.0,
            'factor_breakdown': {},
            'confidence': 'low',
            'explanation': 'Insufficient data for value calculation'
        }

    implied_probability = 1.0 / float(best_decimal_odds)

    # Calculate base score
    base_score = _calculate_base_score(win_rate_pct, implied_probability)

    # Calculate individual factors
    track_factor, track_has_data = _calculate_track_factor(dog_stats, track_name)
    form_factor, form_has_data = _calculate_form_factor(dog_stats)
    trap_factor, trap_has_data, trap_sample_size = _calculate_trap_factor(trap_number)
    time_factor, time_has_data = _calculate_time_factor(race_time)

    # Calculate weighted total score
    total_score = (
        base_score * weights['base_value'] +
        base_score * track_factor * weights['track_factor'] +
        base_score * form_factor * weights['form_factor'] +
        base_score * trap_factor * weights['trap_factor'] +
        base_score * time_factor * weights['time_factor']
    )

    # Build factor breakdown
    factor_breakdown = {
        'base_value': {
            'factor': base_score,
            'weight': weights['base_value'],
            'contribution': base_score * weights['base_value'],
            'has_data': True,
            'description': f'win_rate: {win_rate_pct:.1f}% vs implied: {implied_probability*100:.1f}%'
        },
        'track_factor': {
            'factor': track_factor,
            'weight': weights['track_factor'],
            'contribution': base_score * track_factor * weights['track_factor'],
            'has_data': track_has_data,
            'description': f'+{(track_factor-1)*100:.0f}% at {track_name}' if track_has_data else 'No track data'
        },
        'form_factor': {
            'factor': form_factor,
            'weight': weights['form_factor'],
            'contribution': base_score * form_factor * weights['form_factor'],
            'has_data': form_has_data,
            'description': _get_form_description(form_factor) if form_has_data else 'No form data'
        },
        'trap_factor': {
            'factor': trap_factor,
            'weight': weights['trap_factor'],
            'contribution': base_score * trap_factor * weights['trap_factor'],
            'has_data': trap_has_data,
            'description': f'Trap {trap_number}: {trap_factor*16.67:.1f}%' if trap_has_data else 'No trap data'
        },
        'time_factor': {
            'factor': time_factor,
            'weight': weights['time_factor'],
            'contribution': base_score * time_factor * weights['time_factor'],
            'has_data': time_has_data,
            'description': _get_time_description(race_time, time_factor) if time_has_data else 'No time data'
        }
    }

    # Determine confidence level
    confidence = _determine_confidence(
        track_has_data, form_has_data, trap_has_data, time_has_data, trap_sample_size
    )

    # Generate explanation
    explanation = _generate_explanation(
        win_rate_pct, implied_probability, total_score, confidence, factor_breakdown
    )

    return {
        'total_score': round(total_score, 4),
        'base_score': round(base_score, 4),
        'factor_breakdown': factor_breakdown,
        'confidence': confidence,
        'explanation': explanation
    }


def _get_form_description(form_factor: float) -> str:
    """Generate human-readable form description."""
    if form_factor >= 1.15:
        return 'Strong form'
    elif form_factor >= 1.0:
        return 'Moderate form'
    else:
        return 'Weak form'


def _get_time_description(race_time: Optional[datetime], time_factor: float) -> str:
    """Generate human-readable time slot description."""
    if race_time is None:
        return 'Unknown time'

    hour = race_time.hour
    if hour < 14:
        slot = 'Morning'
    elif hour < 18:
        slot = 'Afternoon'
    else:
        slot = 'Evening'

    diff_pct = (time_factor - 1) * 100
    sign = '+' if diff_pct >= 0 else ''
    return f'{slot} {sign}{diff_pct:.0f}%'


def _generate_explanation(
    win_rate_pct: float,
    implied_probability: float,
    total_score: float,
    confidence: str,
    factor_breakdown: Dict[str, Dict]
) -> str:
    """Generate human-readable explanation of the advanced score."""
    implied_pct = implied_probability * 100

    # Determine value level
    if total_score >= 1.5:
        value_level = 'Strong value'
    elif total_score >= 1.25:
        value_level = 'Good value'
    elif total_score >= 1.1:
        value_level = 'Marginal value'
    else:
        value_level = 'No significant value'

    # Highlight active factors
    active_factors = []
    for name, data in factor_breakdown.items():
        if name == 'base_value':
            continue
        if data['has_data'] and abs(data['factor'] - 1.0) > 0.01:
            if data['factor'] > 1.0:
                active_factors.append(f"+{name.replace('_', ' ')}")
            else:
                active_factors.append(f"-{name.replace('_', ' ')}")

    factors_str = ', '.join(active_factors) if active_factors else 'no adjustments'

    return f"{value_level}: {win_rate_pct:.1f}% win rate vs {implied_pct:.1f}% implied ({factors_str}) [{confidence.upper()} confidence]"

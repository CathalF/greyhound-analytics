"""
Pattern Analysis Routes

Routes for displaying pattern analysis and betting performance insights.
"""

from flask import Blueprint, render_template
from datetime import datetime
import logging

from src.services.pattern_analyzer import (
    get_betting_summary,
    get_track_performance,
    get_value_score_performance,
    get_trap_bias,
    get_time_of_day_analysis
)

# Set up logging
logger = logging.getLogger(__name__)

patterns_bp = Blueprint('patterns', __name__)


@patterns_bp.route('/patterns')
def patterns():
    """
    Pattern analysis page showing betting performance insights.

    Displays:
    - Overall betting summary (win rate, ROI, streak)
    - Track performance breakdown
    - Value score bucket analysis
    - Trap bias statistics
    - Time of day performance
    """
    error_message = None

    try:
        # Gather all pattern data
        summary = get_betting_summary()
        tracks = get_track_performance()
        value_buckets = get_value_score_performance()
        trap_bias = get_trap_bias()
        time_analysis = get_time_of_day_analysis()

    except Exception as e:
        logger.error(f"Error loading pattern analysis: {e}")
        error_message = "Failed to load pattern analysis data. Please try again later."
        summary = {}
        tracks = {}
        value_buckets = {}
        trap_bias = {}
        time_analysis = {}

    return render_template('patterns.html',
                           summary=summary,
                           tracks=tracks,
                           value_buckets=value_buckets,
                           trap_bias=trap_bias,
                           time_analysis=time_analysis,
                           error_message=error_message,
                           current_time=datetime.now())

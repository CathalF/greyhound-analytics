#!/usr/bin/env python
"""
Pattern Analysis CLI

Command-line tool for running pattern analysis on betting history.
Analyzes track performance, value score effectiveness, trap bias, and more.

Usage:
    python src/analyze_patterns.py                # Full analysis report
    python src/analyze_patterns.py --tracks       # Track performance only
    python src/analyze_patterns.py --traps        # Trap bias only
    python src/analyze_patterns.py --value        # Value score buckets only
    python src/analyze_patterns.py --summary      # Summary stats only
    python src/analyze_patterns.py --json         # Output as JSON
"""

import argparse
import json
import logging
import sys

from src.services.pattern_analyzer import (
    get_track_performance,
    get_value_score_performance,
    get_form_correlation,
    get_trap_bias,
    get_time_of_day_analysis,
    get_betting_summary
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_summary(summary: dict) -> str:
    """Format betting summary for display."""
    lines = [
        "=== Betting Performance Summary ===",
        f"Total bets: {summary['total_bets']} | Wins: {summary['wins']} | Losses: {summary['losses']} | Pending: {summary['pending']}",
        f"Win rate: {summary['win_rate']:.1f}% | ROI: {summary['roi']:+.1f}%",
        f"Total profit: {summary['total_profit']:+.2f} units",
        "",
        f"Best track: {summary['best_track']['name']} (ROI: {summary['best_track']['roi']:+.1f}%)",
        f"Worst track: {summary['worst_track']['name']} (ROI: {summary['worst_track']['roi']:+.1f}%)",
        f"Best value bucket: {summary['best_value_bucket']['range']} (ROI: {summary['best_value_bucket']['roi']:+.1f}%)",
        f"Current streak: {summary['current_streak']['count']} {summary['current_streak']['type']}(s)"
    ]
    return "\n".join(lines)


def format_tracks(track_perf: dict) -> str:
    """Format track performance for display."""
    if not track_perf:
        return "=== Track Performance ===\nNo data available.\n"

    lines = ["=== Track Performance ==="]

    # Sort by sample size (most data first)
    sorted_tracks = sorted(track_perf.items(), key=lambda x: x[1]['sample_size'], reverse=True)

    for track_name, stats in sorted_tracks:
        win_rate = stats['win_rate']
        roi = stats['roi']
        sample = stats['sample_size']
        wins = stats['win_count']

        roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
        lines.append(f"{track_name:15} {sample:3} bets, {wins:2} wins ({win_rate:5.1f}%), ROI: {roi_str:>8}")

    return "\n".join(lines)


def format_value_scores(value_perf: dict) -> str:
    """Format value score analysis for display."""
    if not value_perf:
        return "=== Value Score Analysis ===\nNo data available.\n"

    lines = ["=== Value Score Analysis ==="]

    # Sort by bucket range
    bucket_order = ['1.2-1.3', '1.3-1.4', '1.4-1.5', '1.5-2.0', '2.0+']

    for bucket in bucket_order:
        if bucket not in value_perf:
            continue
        stats = value_perf[bucket]
        win_rate = stats['win_rate']
        roi = stats['roi']
        sample = stats['sample_size']
        wins = stats['win_count']
        avg_odds = stats['avg_odds']

        roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
        lines.append(f"{bucket:10} {sample:3} bets, {wins:2} wins ({win_rate:5.1f}%), avg odds: {avg_odds:.2f}, ROI: {roi_str:>8}")

    return "\n".join(lines)


def format_traps(trap_bias: dict) -> str:
    """Format trap bias for display."""
    if not trap_bias or all(t['total_races'] == 0 for t in trap_bias.values()):
        return "=== Trap Bias ===\nNo data available.\n"

    lines = ["=== Trap Bias ==="]

    trap_strs = []
    for trap_num in range(1, 7):
        if trap_num in trap_bias:
            win_rate = trap_bias[trap_num]['win_rate']
            trap_strs.append(f"Trap {trap_num}: {win_rate:5.1f}%")
        else:
            trap_strs.append(f"Trap {trap_num}: N/A")

    lines.append(" | ".join(trap_strs[:3]))
    lines.append(" | ".join(trap_strs[3:]))

    return "\n".join(lines)


def format_form(form_corr: dict) -> str:
    """Format form correlation for display."""
    if not form_corr:
        return "=== Form Correlation ===\nNo data available.\n"

    lines = ["=== Form Correlation ==="]

    form_order = ['strong_form', 'moderate_form', 'weak_form', 'unknown_form']
    form_labels = {
        'strong_form': 'Strong (3+ wins in 5)',
        'moderate_form': 'Moderate (1-2 wins)',
        'weak_form': 'Weak (0 wins)',
        'unknown_form': 'Unknown'
    }

    for form in form_order:
        if form not in form_corr:
            continue
        stats = form_corr[form]
        label = form_labels.get(form, form)
        win_rate = stats['win_rate']
        sample = stats['sample_size']
        avg_value = stats['avg_value_score']

        lines.append(f"{label:25} {sample:3} bets, win rate: {win_rate:5.1f}%, avg value: {avg_value:.2f}")

    return "\n".join(lines)


def format_time_of_day(time_analysis: dict) -> str:
    """Format time of day analysis for display."""
    if not time_analysis:
        return "=== Time of Day Analysis ===\nNo data available.\n"

    lines = ["=== Time of Day Analysis ==="]

    slot_order = ['morning', 'afternoon', 'evening']
    slot_labels = {
        'morning': 'Morning (< 14:00)',
        'afternoon': 'Afternoon (14:00-18:00)',
        'evening': 'Evening (> 18:00)'
    }

    for slot in slot_order:
        if slot not in time_analysis:
            continue
        stats = time_analysis[slot]
        label = slot_labels.get(slot, slot)
        win_rate = stats['win_rate']
        roi = stats['roi']
        sample = stats['sample_size']

        roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
        lines.append(f"{label:25} {sample:3} bets, win rate: {win_rate:5.1f}%, ROI: {roi_str:>8}")

    return "\n".join(lines)


def run_full_analysis() -> dict:
    """Run all pattern analysis functions and return results."""
    return {
        'summary': get_betting_summary(),
        'tracks': get_track_performance(),
        'value_scores': get_value_score_performance(),
        'traps': get_trap_bias(),
        'form': get_form_correlation(),
        'time_of_day': get_time_of_day_analysis()
    }


def main():
    parser = argparse.ArgumentParser(
        description='Pattern Analysis CLI for Greyhound Racing Value Finder'
    )

    parser.add_argument(
        '--tracks', action='store_true',
        help='Show track performance only'
    )
    parser.add_argument(
        '--traps', action='store_true',
        help='Show trap bias only'
    )
    parser.add_argument(
        '--value', action='store_true',
        help='Show value score analysis only'
    )
    parser.add_argument(
        '--summary', action='store_true',
        help='Show summary stats only'
    )
    parser.add_argument(
        '--form', action='store_true',
        help='Show form correlation only'
    )
    parser.add_argument(
        '--time', action='store_true',
        help='Show time of day analysis only'
    )
    parser.add_argument(
        '--json', action='store_true',
        help='Output as JSON (for programmatic use)'
    )

    args = parser.parse_args()

    # Determine what to show
    show_all = not any([args.tracks, args.traps, args.value, args.summary, args.form, args.time])

    # Collect data based on what's needed
    data = {}

    if show_all or args.summary:
        data['summary'] = get_betting_summary()

    if show_all or args.tracks:
        data['tracks'] = get_track_performance()

    if show_all or args.value:
        data['value_scores'] = get_value_score_performance()

    if show_all or args.traps:
        data['traps'] = get_trap_bias()

    if show_all or args.form:
        data['form'] = get_form_correlation()

    if show_all or args.time:
        data['time_of_day'] = get_time_of_day_analysis()

    # Output format
    if args.json:
        # Convert trap bias keys to strings for JSON
        if 'traps' in data:
            data['traps'] = {str(k): v for k, v in data['traps'].items()}
        print(json.dumps(data, indent=2, default=str))
    else:
        # Text output
        output_parts = []

        if 'summary' in data:
            output_parts.append(format_summary(data['summary']))

        if 'tracks' in data:
            output_parts.append(format_tracks(data['tracks']))

        if 'value_scores' in data:
            output_parts.append(format_value_scores(data['value_scores']))

        if 'traps' in data:
            output_parts.append(format_traps(data['traps']))

        if 'form' in data:
            output_parts.append(format_form(data['form']))

        if 'time_of_day' in data:
            output_parts.append(format_time_of_day(data['time_of_day']))

        print("\n\n".join(output_parts))


if __name__ == '__main__':
    main()

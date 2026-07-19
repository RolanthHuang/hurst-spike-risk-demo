"""Command-line interface."""

from __future__ import annotations

import argparse
import json

from .analysis import AnalysisConfig, analyze
from .io import ALLOWED_FEATURES, read_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank feature values by cross-day Hurst change and capture users in spike windows."
    )
    parser.add_argument("--input", required=True, help="Normalized UTF-8 CSV")
    parser.add_argument("--output-dir", default="results", help="Artifact directory")
    parser.add_argument("--feature", choices=sorted(ALLOWED_FEATURES), default="device_type")
    parser.add_argument("--interval-seconds", type=int, default=480)
    parser.add_argument("--top-n-by-volume", type=int, default=40)
    parser.add_argument("--top-n-risk", type=int, default=3)
    parser.add_argument("--delta-threshold", type=float, default=0.20)
    parser.add_argument("--jump-ratio", type=float, default=3.0)
    parser.add_argument("--target-window", type=int, default=25)
    parser.add_argument("--min-events-per-day", type=int, default=20)
    parser.add_argument("--min-spike-count", type=int, default=4)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = AnalysisConfig(
        feature=args.feature,
        interval_seconds=args.interval_seconds,
        top_n_by_volume=args.top_n_by_volume,
        top_n_risk=args.top_n_risk,
        delta_threshold=args.delta_threshold,
        jump_ratio=args.jump_ratio,
        target_window=args.target_window,
        min_events_per_day=args.min_events_per_day,
        min_spike_count=args.min_spike_count,
    )
    metadata = analyze(read_events(args.input), args.output_dir, config)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


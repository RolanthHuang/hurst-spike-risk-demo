"""End-to-end analysis and artifact generation."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .core import fractal_dimension_from_hurst, hurst_dfa, spike_flags
from .io import Event


@dataclass(frozen=True)
class AnalysisConfig:
    feature: str = "device_type"
    interval_seconds: int = 480
    top_n_by_volume: int = 40
    top_n_risk: int = 3
    delta_threshold: float = 0.20
    jump_ratio: float = 3.0
    target_window: int = 25
    min_events_per_day: int = 20
    min_spike_count: int = 4


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"feature_{digest}"


def _day_bins(
    events: list[Event], interval_seconds: int
) -> tuple[np.ndarray, dict[int, list[Event]]]:
    bins_per_day = 86400 // interval_seconds
    counts = np.zeros(bins_per_day, dtype=float)
    bin_events: dict[int, list[Event]] = defaultdict(list)
    for event in events:
        utc = event.event_time.astimezone(timezone.utc)
        seconds = utc.hour * 3600 + utc.minute * 60 + utc.second
        index = min(seconds // interval_seconds, bins_per_day - 1)
        counts[index] += 1
        bin_events[int(index)].append(event)
    return counts, bin_events


def analyze(
    events: list[Event], output_dir: str | Path, config: AnalysisConfig
) -> dict[str, int | float | str]:
    if 86400 % config.interval_seconds != 0:
        raise ValueError("interval_seconds must divide 86400 exactly")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    by_feature_day: dict[str, dict[date, list[Event]]] = defaultdict(
        lambda: defaultdict(list)
    )
    volume = Counter()
    for event in events:
        feature_value = event.feature_value(config.feature)
        day = event.event_time.astimezone(timezone.utc).date()
        by_feature_day[feature_value][day].append(event)
        volume[feature_value] += 1

    considered = {
        feature_value
        for feature_value, _ in volume.most_common(config.top_n_by_volume)
    }

    hurst_rows: list[dict] = []
    hurst_by_feature: dict[str, list[float]] = defaultdict(list)
    for feature_value in sorted(considered):
        for day, day_events in sorted(by_feature_day[feature_value].items()):
            if len(day_events) < config.min_events_per_day:
                continue
            counts, _ = _day_bins(day_events, config.interval_seconds)
            hurst = hurst_dfa(counts)
            if not np.isfinite(hurst):
                continue
            hurst_by_feature[feature_value].append(hurst)
            hurst_rows.append(
                {
                    "feature": config.feature,
                    "feature_value": feature_value,
                    "day_utc": day.isoformat(),
                    "event_count": len(day_events),
                    "hurst_exponent": f"{hurst:.6f}",
                    "graph_fractal_dimension": (
                        f"{fractal_dimension_from_hurst(hurst):.6f}"
                    ),
                }
            )

    summary_rows: list[dict] = []
    for feature_value in sorted(considered):
        values = hurst_by_feature.get(feature_value, [])
        delta = max(values) - min(values) if len(values) >= 2 else 0.0
        summary_rows.append(
            {
                "feature": config.feature,
                "feature_value": feature_value,
                "total_events": volume[feature_value],
                "days_with_hurst": len(values),
                "min_hurst": f"{min(values):.6f}" if values else "",
                "max_hurst": f"{max(values):.6f}" if values else "",
                "delta_hurst": f"{delta:.6f}",
                "passes_delta_threshold": str(
                    len(values) >= 2 and delta >= config.delta_threshold
                ).lower(),
            }
        )

    summary_rows.sort(key=lambda row: float(row["delta_hurst"]), reverse=True)
    eligible = [
        row
        for row in summary_rows
        if row["passes_delta_threshold"] == "true"
    ][: config.top_n_risk]
    risk_values = {str(row["feature_value"]) for row in eligible}

    spike_rows: list[dict] = []
    captured = Counter()
    spike_plot_data: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for feature_value in sorted(risk_values):
        aggregate_counts: list[np.ndarray] = []
        aggregate_flags: list[np.ndarray] = []
        for day, day_events in sorted(by_feature_day[feature_value].items()):
            counts, bin_events = _day_bins(day_events, config.interval_seconds)
            flags, baselines = spike_flags(
                counts,
                jump_ratio=config.jump_ratio,
                target_window=config.target_window,
                min_spike_count=config.min_spike_count,
            )
            aggregate_counts.append(counts)
            aggregate_flags.append(flags)
            for index in np.flatnonzero(flags):
                start = datetime.combine(day, time.min, tzinfo=timezone.utc) + timedelta(
                    seconds=int(index) * config.interval_seconds
                )
                end = start + timedelta(seconds=config.interval_seconds)
                users = sorted({event.user_id for event in bin_events[int(index)]})
                for user_id in users:
                    captured[user_id] += 1
                spike_rows.append(
                    {
                        "feature": config.feature,
                        "feature_value": feature_value,
                        "window_start_utc": start.isoformat().replace("+00:00", "Z"),
                        "window_end_utc": end.isoformat().replace("+00:00", "Z"),
                        "event_count": int(counts[index]),
                        "baseline": f"{baselines[index]:.3f}",
                        "unique_users": len(users),
                        "user_ids": ";".join(users),
                    }
                )
        if aggregate_counts:
            spike_plot_data[feature_value] = (
                np.concatenate(aggregate_counts), np.concatenate(aggregate_flags)
            )

    captured_rows = [
        {"user_id": user_id, "spike_window_count": count}
        for user_id, count in captured.most_common()
    ]

    _write_csv(
        output / "hurst_by_day.csv",
        [
            "feature",
            "feature_value",
            "day_utc",
            "event_count",
            "hurst_exponent",
            "graph_fractal_dimension",
        ],
        hurst_rows,
    )
    _write_csv(
        output / "feature_risk_summary.csv",
        [
            "feature",
            "feature_value",
            "total_events",
            "days_with_hurst",
            "min_hurst",
            "max_hurst",
            "delta_hurst",
            "passes_delta_threshold",
        ],
        summary_rows,
    )
    _write_csv(
        output / "spike_windows.csv",
        [
            "feature",
            "feature_value",
            "window_start_utc",
            "window_end_utc",
            "event_count",
            "baseline",
            "unique_users",
            "user_ids",
        ],
        spike_rows,
    )
    _write_csv(
        output / "captured_users.csv",
        ["user_id", "spike_window_count"],
        captured_rows,
    )

    labels = [str(row["feature_value"]) for row in summary_rows]
    deltas = [float(row["delta_hurst"]) for row in summary_rows]
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#d95f02" if label in risk_values else "#4c78a8" for label in labels]
    ax.barh(labels[::-1], deltas[::-1], color=colors[::-1])
    ax.axvline(config.delta_threshold, color="#333333", linestyle="--", label="threshold")
    ax.set_xlabel("Cross-day delta H (max H - min H)")
    ax.set_title(f"Risk ranking by {config.feature}")
    ax.grid(axis="x", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "risk_overview.png", dpi=180)
    plt.close(fig)

    for feature_value, (counts, flags) in spike_plot_data.items():
        x_axis = np.arange(counts.size)
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x_axis, counts, color="#4c78a8", linewidth=0.9, label="event count")
        if np.any(flags):
            ax.scatter(
                x_axis[flags], counts[flags], color="#d95f02", s=28, label="captured spike"
            )
        ax.set_xlabel("Time bucket across analyzed UTC days")
        ax.set_ylabel("Events")
        ax.set_title(f"Spike capture: {feature_value}")
        ax.grid(alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output / f"spikes_{_safe_name(feature_value)}.png", dpi=180)
        plt.close(fig)

    metadata = {
        "feature": config.feature,
        "input_event_count": len(events),
        "considered_feature_values": len(considered),
        "risk_feature_values": len(risk_values),
        "spike_windows": len(spike_rows),
        "captured_users": len(captured_rows),
        "parameters": config.__dict__,
    }
    (output / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


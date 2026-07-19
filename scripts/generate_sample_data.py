"""Generate a deterministic, entirely synthetic event dataset."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


def generate(output: Path, seed: int = 20260719) -> None:
    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    interval_seconds = 480
    bins_per_day = 86400 // interval_seconds
    rows: list[dict[str, str]] = []

    feature_profiles = {
        "Browser": "steady",
        "Mobile": "steady",
        "Emulator": "changing",
    }
    benign_users = [f"demo_user_{index:03d}" for index in range(1, 41)]
    injected_users = ["demo_suspect_a", "demo_suspect_b", "demo_suspect_c"]

    for day_index in range(7):
        for device_index, (device_type, profile) in enumerate(feature_profiles.items()):
            if profile == "steady":
                base_rate = 1.25 if device_type == "Browser" else 1.0
                counts = rng.poisson(base_rate, size=bins_per_day)
            elif day_index < 3:
                counts = rng.poisson(0.75, size=bins_per_day)
            else:
                smooth = 0.20 + 1.8 * (np.sin(np.linspace(0, 3 * np.pi, bins_per_day)) + 1) / 2
                counts = rng.poisson(smooth)
                for spike_index in (44, 96, 142):
                    counts[spike_index] += 18 + day_index
            for bin_index, count in enumerate(counts):
                for event_index in range(int(count)):
                    second_offset = int(rng.integers(0, interval_seconds))
                    event_time = start + timedelta(
                        days=day_index,
                        seconds=bin_index * interval_seconds + second_offset,
                    )
                    is_injected = (
                        profile == "changing"
                        and day_index >= 3
                        and bin_index in (44, 96, 142)
                    )
                    user_id = (
                        injected_users[event_index % len(injected_users)]
                        if is_injected
                        else str(rng.choice(benign_users))
                    )
                    documentation_ip = (
                        f"192.0.2.{10 + device_index}"
                        if profile == "steady"
                        else "198.51.100.77"
                    )
                    rows.append(
                        {
                            "event_time": event_time.isoformat().replace("+00:00", "Z"),
                            "user_id": user_id,
                            "ip": documentation_ip,
                            "device_id": f"demo_device_{device_index + 1:02d}",
                            "device_type": device_type,
                        }
                    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["event_time", "user_id", "ip", "device_id", "device_type"],
        )
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["event_time"]))
    print(f"Wrote {len(rows)} synthetic events to {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/sample_events.csv", type=Path)
    parser.add_argument("--seed", type=int, default=20260719)
    args = parser.parse_args()
    generate(args.output, args.seed)


if __name__ == "__main__":
    main()


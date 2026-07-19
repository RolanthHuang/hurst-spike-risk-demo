"""Input validation and normalization."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_COLUMNS = {
    "event_time",
    "user_id",
    "ip",
    "device_id",
    "device_type",
}
ALLOWED_FEATURES = {"ip", "device_id", "device_type"}


@dataclass(frozen=True)
class Event:
    event_time: datetime
    user_id: str
    ip: str
    device_id: str
    device_type: str

    def feature_value(self, feature: str) -> str:
        if feature not in ALLOWED_FEATURES:
            raise ValueError(f"Unsupported feature: {feature}")
        return str(getattr(self, feature))


def parse_utc_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError(f"Timezone is required: {value!r}")
    return parsed.astimezone(timezone.utc)


def read_events(path: str | Path) -> list[Event]:
    source = Path(path)
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Missing input columns: {sorted(missing)}")

        events: list[Event] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                event = Event(
                    event_time=parse_utc_timestamp(row["event_time"]),
                    user_id=row["user_id"].strip(),
                    ip=row["ip"].strip(),
                    device_id=row["device_id"].strip(),
                    device_type=row["device_type"].strip(),
                )
            except Exception as exc:
                raise ValueError(f"Invalid row {row_number}: {exc}") from exc
            if not all(
                [event.user_id, event.ip, event.device_id, event.device_type]
            ):
                raise ValueError(f"Blank required value in row {row_number}")
            events.append(event)

    if not events:
        raise ValueError("Input contains no events")
    return sorted(events, key=lambda event: event.event_time)


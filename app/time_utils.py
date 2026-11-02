from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


def to_iso(value: datetime) -> str:
    """Format a datetime as a second-precision UTC ISO 8601 timestamp."""
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")

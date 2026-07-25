from datetime import datetime, timezone


def elapsed_seconds(start: datetime, end: datetime) -> int:
    """Return a non-negative elapsed duration across database timezone dialects."""
    if start.tzinfo is None:
        end = end.replace(tzinfo=None)
    elif end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    return max(int((end - start).total_seconds()), 0)

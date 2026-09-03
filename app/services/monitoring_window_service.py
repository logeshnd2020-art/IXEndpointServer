from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy.orm import Session as DBSession

from app.models.device_heartbeat import DeviceHeartbeat


# A segment is (start: datetime, end: datetime, monitored: bool).
Segment = Tuple[datetime, datetime, bool]


class MonitoringWindowService:
    """
    Derives which parts of a time window were actually observed by the
    agent, using gaps between consecutive `device_heartbeats` rows as the
    signal.

    This is the server's own, independently-verifiable source for
    monitored/not-monitored time. `sessions.duration_seconds` (the
    agent's own claimed monitored-awake total) is deliberately not used
    here or anywhere else in the accounting pipeline: once an agent
    version started actually reporting it, empirical comparison against
    this heartbeat evidence showed it under-excluding even a single,
    unambiguous multi-hour sleep gap by a wide margin, so it isn't
    treated as authoritative when it disagrees with what the server can
    verify for itself. A gap between heartbeats materially larger than
    the agent's normal cadence means the device was not being observed
    for that interval -- consistent with sleep, but also consistent with
    the agent process not running while the machine stayed awake. The
    two cannot be distinguished with the data available today, so both
    are reported as a single, honest "not monitored" segment rather than
    a fabricated SLEEP/UNKNOWN split.

    A window with no heartbeat coverage at all (e.g. a device/session with
    zero heartbeat rows) has no evidence of a gap either way, so it is
    treated as fully monitored -- this preserves the pre-existing
    wall-clock behavior for data that predates or never sent heartbeats,
    rather than inventing a gap that isn't supported by any data.
    """

    # Observed heartbeat cadence is roughly every 30 seconds. A threshold
    # of 180s (~4-6 missed heartbeats) is comfortably above normal network
    # jitter/retry noise while still catching real gaps quickly.
    DEFAULT_GAP_THRESHOLD_SECONDS = 180

    @staticmethod
    def _normalize(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def get_segments(
        db: DBSession,
        device_id: int,
        window_start: datetime,
        window_end: datetime,
        gap_threshold_seconds: int = DEFAULT_GAP_THRESHOLD_SECONDS,
    ) -> List[Segment]:
        """
        Partition [window_start, window_end] into ordered segments, each
        tagged `monitored=True` (heartbeats present at normal cadence) or
        `monitored=False` (a heartbeat gap at least gap_threshold_seconds
        long fell inside the window).
        """
        window_start = MonitoringWindowService._normalize(window_start)
        window_end = MonitoringWindowService._normalize(window_end)

        if window_end <= window_start:
            return []

        heartbeats = (
            db.query(DeviceHeartbeat.timestamp)
            .filter(
                DeviceHeartbeat.device_id == device_id,
                DeviceHeartbeat.timestamp >= window_start,
                DeviceHeartbeat.timestamp <= window_end,
            )
            .order_by(DeviceHeartbeat.timestamp.asc())
            .all()
        )

        timestamps = [MonitoringWindowService._normalize(row[0]) for row in heartbeats]

        if not timestamps:
            # No heartbeat evidence at all inside this window -- assume
            # fully monitored rather than inventing a gap.
            return [(window_start, window_end, True)]

        segments: List[Segment] = []
        cursor = window_start

        # Gap between the start of the window and the first heartbeat we
        # actually observed.
        first = timestamps[0]
        if (first - cursor).total_seconds() > gap_threshold_seconds:
            segments.append((cursor, first, False))
            cursor = first
        elif first > cursor:
            segments.append((cursor, first, True))
            cursor = first

        # Gaps between consecutive heartbeats.
        for prev_ts, next_ts in zip(timestamps, timestamps[1:]):
            if next_ts <= cursor:
                continue

            gap_seconds = (next_ts - prev_ts).total_seconds()

            if gap_seconds > gap_threshold_seconds:
                segments.append((prev_ts, next_ts, False))
            else:
                segments.append((cursor, next_ts, True))

            cursor = next_ts

        # Tail: from the last heartbeat to the end of the window.
        last = timestamps[-1]
        if (window_end - last).total_seconds() > gap_threshold_seconds:
            segments.append((last, window_end, False))
        elif window_end > cursor:
            segments.append((cursor, window_end, True))

        # Merge adjacent segments of the same type for a cleaner partition.
        merged: List[Segment] = []
        for seg in segments:
            if merged and merged[-1][2] == seg[2] and merged[-1][1] == seg[0]:
                prev_start, _, monitored = merged[-1]
                merged[-1] = (prev_start, seg[1], monitored)
            else:
                merged.append(seg)

        return merged

    @staticmethod
    def monitored_seconds(segments: List[Segment]) -> int:
        return sum(
            int((end - start).total_seconds())
            for start, end, monitored in segments
            if monitored
        )

from datetime import datetime, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from app.models.idle import IdleEvent
from app.models.session import Session as UserSession
from app.services.monitoring_window_service import MonitoringWindowService


# Session and idle-event timestamps are stored as naive endpoint-local
# time (IST) -- the same convention ProductivityService/
# ProductivityReportService already use for them. This is distinct from
# device_heartbeats, which are naive UTC (handled inside
# MonitoringWindowService). Mixing the two up would silently misalign a
# session's own boundaries against an externally-supplied window (e.g. a
# report period's day boundary), which is exactly what happened before
# this constant existed -- see CLIENT_LOCAL_TZ usage below.
CLIENT_LOCAL_TZ = ZoneInfo("Asia/Kolkata")


class TimelineService:
    """
    Builds an ordered, contiguous partition of a session's time window into
    ACTIVE / IDLE / SLEEP_GAP segments, using only data the server already
    stores (device_heartbeats via MonitoringWindowService, and idle_events).
    Never fabricates a segment type without supporting data.

    This is the single canonical interval representation for the whole
    app: ProductivityService, ProductivityReportService, and the Activity
    Timeline/Activity Details UI all derive their Active/Idle/Sleep
    figures from `build()`'s output (directly, or via
    `overlap_seconds_by_type()` for a sub-window such as one application's
    usage span) rather than each computing their own idle/gap logic. That
    guarantees they can't disagree with each other about the same
    underlying data.

    Deliberately does not use `session.duration_seconds`. That field was
    originally intended as the agent's own authoritative monitored-awake
    total, but empirical comparison against the server's own heartbeat
    evidence (once the agent started actually reporting it) showed it
    under-excluding even a single, unambiguous multi-hour sleep gap by a
    wide margin -- so it is not treated as authoritative when it disagrees
    with what the server can independently verify from heartbeats and
    idle events.
    """

    @staticmethod
    def _normalize(dt: Optional[datetime]) -> Optional[datetime]:
        """
        For externally-supplied window bounds (e.g. a report period's day
        boundary), which are always already timezone-aware UTC in every
        real call site -- this only matters as a defensive no-op/UTC
        assumption for a bound that happens to arrive naive.
        """
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _normalize_local(dt: Optional[datetime]) -> Optional[datetime]:
        """
        For session.login_time/logout_time and idle_event timestamps,
        which are naive endpoint-local (IST) -- NOT naive UTC. Using
        `_normalize` (UTC-assumed) on these would silently shift a
        session's own boundaries by the IST offset relative to an
        externally-supplied window, which could clip a real day's
        segments to nothing.
        """
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=CLIENT_LOCAL_TZ).astimezone(timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def build(
        db: DBSession,
        session: UserSession,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> List[Dict]:
        """
        Build segments for `session`, either over its own full lifetime
        (default, same as before) or clipped to an explicit
        [window_start, window_end) slice -- used by the per-day timeline,
        where a session may span multiple calendar days and only the
        portion overlapping the requested day should be returned.
        """
        now = datetime.now(timezone.utc)

        session_start = TimelineService._normalize_local(session.login_time)
        session_end = (
            TimelineService._normalize_local(session.logout_time)
            if session.logout_time
            else now
        )

        if session_start is None or session_end <= session_start:
            return []

        if window_start is not None:
            window_start = max(TimelineService._normalize(window_start), session_start)
        else:
            window_start = session_start

        if window_end is not None:
            window_end = min(TimelineService._normalize(window_end), session_end)
        else:
            window_end = session_end

        if window_end <= window_start:
            return []

        gap_segments = MonitoringWindowService.get_segments(
            db,
            session.device_id,
            window_start,
            window_end,
        )

        idle_events = (
            db.query(IdleEvent)
            .filter(IdleEvent.session_id == session.id)
            .order_by(IdleEvent.idle_start.asc())
            .all()
        )

        idle_intervals = []
        for idle in idle_events:
            idle_start = TimelineService._normalize_local(idle.idle_start)
            idle_end = (
                TimelineService._normalize_local(idle.idle_end)
                if idle.idle_end
                else now
            )
            if idle_start and idle_end > idle_start:
                idle_intervals.append((idle_start, idle_end))

        segments: List[Dict] = []

        for seg_start, seg_end, monitored in gap_segments:

            if not monitored:
                segments.append(
                    {
                        "start": seg_start,
                        "end": seg_end,
                        "type": "SLEEP_GAP",
                        "duration_seconds": int((seg_end - seg_start).total_seconds()),
                    }
                )
                continue

            # Split this monitored segment into ACTIVE/IDLE using
            # idle_events overlap, clipped to the segment's own bounds.
            clipped = []
            for idle_start, idle_end in idle_intervals:
                start = max(idle_start, seg_start)
                end = min(idle_end, seg_end)
                if end > start:
                    clipped.append((start, end))
            clipped.sort()

            merged = []
            for start, end in clipped:
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))

            cursor = seg_start

            for idle_start, idle_end in merged:
                if idle_start > cursor:
                    segments.append(
                        {
                            "start": cursor,
                            "end": idle_start,
                            "type": "ACTIVE",
                            "duration_seconds": int((idle_start - cursor).total_seconds()),
                        }
                    )
                segments.append(
                    {
                        "start": idle_start,
                        "end": idle_end,
                        "type": "IDLE",
                        "duration_seconds": int((idle_end - idle_start).total_seconds()),
                    }
                )
                cursor = idle_end

            if cursor < seg_end:
                segments.append(
                    {
                        "start": cursor,
                        "end": seg_end,
                        "type": "ACTIVE",
                        "duration_seconds": int((seg_end - cursor).total_seconds()),
                    }
                )

        return segments

    @staticmethod
    def totals_by_type(segments: List[Dict]) -> Dict[str, int]:
        """Sums duration_seconds per segment type -- e.g. {"ACTIVE": 123, "IDLE": 45}."""
        totals: Dict[str, int] = {}
        for seg in segments:
            totals[seg["type"]] = totals.get(seg["type"], 0) + seg["duration_seconds"]
        return totals

    @staticmethod
    def overlap_seconds_by_type(segments: List[Dict], start: Optional[datetime], end: Optional[datetime]) -> Dict[str, int]:
        """
        Intersects [start, end) (e.g. one application's usage span) against
        the canonical segments and sums overlap seconds per type. Used to
        scope a sub-window's Active/Idle to the same monitored/gap
        boundaries the session-level totals already respect -- so, e.g.,
        an application never gets credited with idle or active time during
        a stretch the device wasn't even being observed (SLEEP_GAP), the
        same way session-level totals already exclude it.
        """
        start = TimelineService._normalize(start)
        end = TimelineService._normalize(end)

        totals: Dict[str, int] = {}

        if start is None or end is None or end <= start:
            return totals

        for seg in segments:
            ov_start = max(seg["start"], start)
            ov_end = min(seg["end"], end)
            if ov_end > ov_start:
                totals[seg["type"]] = totals.get(seg["type"], 0) + int((ov_end - ov_start).total_seconds())

        return totals

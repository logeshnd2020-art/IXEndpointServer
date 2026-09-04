from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from app.models.idle import IdleEvent
from app.models.session import Session as UserSession
from app.services.monitoring_window_service import MonitoringWindowService
from app.services.work_session_service import WorkSessionClassifier


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
    ACTIVE / IDLE / SLEEP_CONFIRMED / MONITORING_GAP / OFF_SESSION segments,
    using only data the server already stores (device_heartbeats via
    MonitoringWindowService, and idle_events). Never fabricates a segment
    type without supporting data, and never uses clock time, day of week,
    or any fixed schedule to classify anything -- see WorkSessionClassifier
    for the gap-classification rules specifically.

    This is the single canonical interval representation for the whole
    app: ProductivityService, ProductivityReportService, Application
    attribution, and the Activity Timeline/Activity Details UI all derive
    their Active/Idle/Sleep/Off-Session figures from `build()`'s output
    (directly, or via `overlap_seconds_by_type()` for a sub-window such as
    one application's usage span) rather than each computing their own
    idle/gap/session-boundary logic. That guarantees they can't disagree
    with each other about the same underlying data -- it is structurally
    impossible for the same interval to be Sleep/Gap/Off-Session in
    Timeline but Active in Application attribution or Productivity,
    because none of them classifies independently.

    Deliberately does not use `session.duration_seconds`. That field was
    originally intended as the agent's own authoritative monitored-awake
    total, but empirical comparison against the server's own heartbeat
    evidence (once the agent started actually reporting it) showed it
    under-excluding even a single, unambiguous multi-hour sleep gap by a
    wide margin -- so it is not treated as authoritative when it disagrees
    with what the server can independently verify from heartbeats and
    idle events.
    """

    # A run/gap that starts or ends outside the caller's requested display
    # window (e.g. a work session crossing a report day's midnight
    # boundary) must still be evaluated with its full true context, not a
    # truncated one -- otherwise a continuous confirmed run spanning
    # midnight could be wrongly split or a gap's flanking evidence could be
    # missed at the display window's own edge. Classification therefore
    # always runs over [display_start - PADDING, display_end + PADDING]
    # (clamped to the session's own true lifetime); the caller's originally
    # requested window is applied only as a final clip, AFTER
    # classification, never before. 2 hours is comfortably larger than
    # OFF_SESSION_CEILING_SECONDS (1h) and SUSTAINED_RUN_SECONDS (3min) --
    # the two values any classification decision actually needs to
    # resolve -- while remaining a small, bounded, indexed-query addition.
    PADDING = timedelta(hours=2)

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
            display_start = max(TimelineService._normalize(window_start), session_start)
        else:
            display_start = session_start

        if window_end is not None:
            display_end = min(TimelineService._normalize(window_end), session_end)
        else:
            display_end = session_end

        if display_end <= display_start:
            return []

        # Classification always sees the padded window (clamped to the
        # session's own true lifetime -- there is no valid evidence
        # outside it anyway); the caller's requested [display_start,
        # display_end) is applied only as a final clip, at the very end.
        eval_start = max(session_start, display_start - TimelineService.PADDING)
        eval_end = min(session_end, display_end + TimelineService.PADDING)

        gap_segments = MonitoringWindowService.get_segments(
            db,
            session.device_id,
            eval_start,
            eval_end,
        )

        classified_segments = WorkSessionClassifier.classify(gap_segments)

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

        for seg in classified_segments:
            seg_start, seg_end = seg["start"], seg["end"]

            if not seg["monitored"]:
                # gap_type is one of SLEEP_CONFIRMED, MONITORING_GAP, or
                # OFF_SESSION -- decided entirely by WorkSessionClassifier,
                # never here. This function never overrides or re-derives
                # that decision.
                segments.append(
                    {
                        "start": seg_start,
                        "end": seg_end,
                        "type": seg["gap_type"],
                        "duration_seconds": int((seg_end - seg_start).total_seconds()),
                    }
                )
                continue

            # Split this confirmed monitored segment into ACTIVE/IDLE
            # using idle_events overlap, clipped to the segment's own
            # bounds -- unchanged logic from before.
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

        # Clip the fully-classified segment list down to exactly the
        # originally requested display window -- arithmetic intersection
        # only, never a re-classification. A segment straddling the clip
        # boundary (e.g. a confirmed run crossing midnight, viewed one
        # calendar day at a time) is split into two same-type rows here,
        # with their combined duration exactly equal to the unclipped
        # segment's own duration.
        return TimelineService._clip_segments(segments, display_start, display_end)

    @staticmethod
    def _clip_segments(segments: List[Dict], clip_start: datetime, clip_end: datetime) -> List[Dict]:
        clipped: List[Dict] = []
        for seg in segments:
            start = max(seg["start"], clip_start)
            end = min(seg["end"], clip_end)
            if end > start:
                new_seg = dict(seg)
                new_seg["start"] = start
                new_seg["end"] = end
                new_seg["duration_seconds"] = int((end - start).total_seconds())
                clipped.append(new_seg)
        return clipped

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
        a stretch the device wasn't even being observed (SLEEP_CONFIRMED,
        MONITORING_GAP, or OFF_SESSION), the same way session-level totals
        already exclude those types. Callers achieve the exclusion simply
        by only ever reading the "ACTIVE"/"IDLE" keys out of this
        function's return value -- any other type key present is never
        looked at, so it can never contribute to Active/Idle attribution.
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

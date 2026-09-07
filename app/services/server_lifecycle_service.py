"""
Phase 3, Item 2 -- server lifecycle evidence: write path and the
conservative outage-interval derivation described in the Phase 3
design spec (Correction 2 / Rule 2).

Two derived confidence tiers, computed fresh from the raw
server_lifecycle_events rows on every call -- never stored directly:

  - CONFIRMED_OUTAGE_INTERVAL ("CONFIRMED"): a "shutdown" row
    immediately followed (no other row of either type in between) by a
    "startup" row. Both boundaries are exact -- "shutdown" fires while
    the process is still alive, "startup" fires at the very start of
    the next process's life.

  - UNCERTAIN_AVAILABILITY_INTERVAL ("UNCERTAIN"): a "startup" row
    immediately followed by a SECOND "startup" row with no "shutdown"
    in between -- i.e. the previous run ended ungracefully (crash,
    hard reboot, power loss, SIGKILL). Something ended that run, but
    the exact moment unavailability began within this span is NOT
    known. This interval must NEVER be reported as a specific,
    confident outage window -- only as "availability could not be
    confirmed for this span."

No other confidence tier exists. In particular, this module never
concludes "available" from the absence of an interval -- absence of
evidence is not evidence of availability (see ServerLifecycleEvent's
docstring for the full rationale). A caller that finds no evidence
overlapping a window must simply have nothing to say about that
window, not assume it was fine.
"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Literal

from sqlalchemy.orm import Session

from app.models.server_lifecycle_event import ServerLifecycleEvent

logger = logging.getLogger("ix.server_lifecycle")

OutageConfidence = Literal["CONFIRMED", "UNCERTAIN"]

# How far outside [window_start, window_end) to look for the lifecycle
# rows that bound an interval straddling the window's edge.
_LOOKAROUND_PAD = timedelta(days=1)


def _normalize(dt: datetime) -> datetime:
    """
    ServerLifecycleEvent.occurred_at is always WRITTEN as aware UTC
    (_safe_record uses datetime.now(timezone.utc) exclusively, never a
    naive value). SQLite, however, has no real timezone-aware column
    type and silently strips tzinfo on round-trip -- the same
    well-documented limitation MonitoringWindowService already works
    around for device_heartbeats.timestamp. A naive value read back
    from this specific column can therefore only mean "the DB dropped
    the tzinfo of an originally-UTC value", so it is re-tagged as UTC,
    never local time -- unlike the naive-IST convention used elsewhere
    in this codebase for agent-supplied timestamps.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class OutageEvidence:
    start: datetime
    end: datetime
    confidence: OutageConfidence

    def overlaps(self, window_start: datetime, window_end: datetime) -> bool:
        return self.start < window_end and self.end > window_start


def _safe_record(db: Session, event_type: str, pid: int) -> None:
    """
    Write one lifecycle row. Never allowed to raise -- a failure to
    record this evidence must never be able to prevent the server from
    actually starting or shutting down. A failed write simply leaves
    that boundary without evidence, which get_outage_evidence() already
    handles correctly ("no event = no conclusion").
    """
    try:
        event = ServerLifecycleEvent(
            event_type=event_type,
            occurred_at=datetime.now(timezone.utc),
            pid=pid,
        )
        db.add(event)
        db.commit()
    except Exception:
        logger.exception(
            "Failed to record server lifecycle event: %s", event_type
        )
        try:
            db.rollback()
        except Exception:
            pass


def record_startup(db: Session) -> None:
    _safe_record(db, "startup", os.getpid())


def record_shutdown(db: Session) -> None:
    _safe_record(db, "shutdown", os.getpid())


def get_outage_evidence(
    db: Session,
    window_start: datetime,
    window_end: datetime,
) -> List[OutageEvidence]:
    """
    Return every CONFIRMED/UNCERTAIN interval that overlaps
    [window_start, window_end), derived fresh from the raw event log.
    Looks slightly outside the window on each side so a pair straddling
    the boundary is still found.
    """
    window_start = _normalize(window_start)
    window_end = _normalize(window_end)

    # SQLite has no real timezone-aware column type and stores
    # occurred_at as a naive string -- bind naive-UTC query bounds so
    # the SQL-level comparison is apples-to-apples with what's actually
    # stored, matching the same pattern MonitoringWindowService already
    # uses for device_heartbeats.timestamp.
    query_start = (window_start - _LOOKAROUND_PAD).replace(tzinfo=None)
    query_end = (window_end + _LOOKAROUND_PAD).replace(tzinfo=None)

    rows = (
        db.query(ServerLifecycleEvent)
        .filter(
            ServerLifecycleEvent.occurred_at >= query_start,
            ServerLifecycleEvent.occurred_at <= query_end,
        )
        .order_by(
            ServerLifecycleEvent.occurred_at.asc(),
            ServerLifecycleEvent.id.asc(),
        )
        .all()
    )

    evidence: List[OutageEvidence] = []

    for prev_row, next_row in zip(rows, rows[1:]):
        prev_at = _normalize(prev_row.occurred_at)
        next_at = _normalize(next_row.occurred_at)

        if prev_row.event_type == "shutdown" and next_row.event_type == "startup":
            interval = OutageEvidence(
                start=prev_at,
                end=next_at,
                confidence="CONFIRMED",
            )
        elif prev_row.event_type == "startup" and next_row.event_type == "startup":
            interval = OutageEvidence(
                start=prev_at,
                end=next_at,
                confidence="UNCERTAIN",
            )
        else:
            # startup -> shutdown (normal running span) or any other
            # adjacency is not outage evidence of any kind.
            continue

        if interval.overlaps(window_start, window_end):
            evidence.append(interval)

    return evidence

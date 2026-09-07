"""
7.8.0 server reason-evidence groundwork -- derives management-facing
`reason` values from raw AgentLifecycleEvent rows (and, as a fallback,
Phase 3's server_lifecycle_events), per the approved 7.8.0 specification.

This module NEVER touches WorkSessionClassifier, MonitoringWindowService,
or TimelineService's decision logic, and never changes a segment's `type`.
It only ever supplies the optional `reason` annotation Phase 3 already
reserved on TimelineSegment -- the classification pipeline is completely
unaware this module exists.

Every derivation here requires at least one positive, stored event as its
anchor. None of them is ever produced from the mere absence of heartbeats
-- a gap with no corroborating evidence simply gets reason=None, exactly
as it did before this module existed (the honest MONITORING_GAP/Unknown
fallback, unchanged).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.agent_lifecycle_event import AgentLifecycleEvent
from app.repositories.agent_lifecycle_repository import AgentLifecycleRepository
from app.services.server_lifecycle_service import get_outage_evidence

# A boottime delta smaller than this is treated as clock jitter (e.g. a
# one-time NTP step), not a real reboot -- see the approved specification,
# section C.3, for the full authoritativeness argument. 60s is comfortably
# larger than any plausible jitter and comfortably smaller than any real
# reboot's elapsed time.
BOOTTIME_TOLERANCE_SECONDS = 60

# How long the gap between SHUTDOWN_OR_RESTART_IMMINENT and the next
# AGENT_STARTED may be and still count as a cooperative, same-cycle
# restart rather than a shutdown followed by a later, separate power-on.
# This is the one explicit duration threshold in this module, named and
# documented exactly as such -- not disguised as pure evidence.
RESTART_VS_SHUTDOWN_GAP_SECONDS = 300

# Reasons are applied to overlapping gap segments in this priority order
# when more than one piece of evidence could apply to the same stretch
# (rare, but possible with unusual event orderings) -- more specific,
# device-observed evidence wins over the more generic server-side
# fallback.
_REASON_PRIORITY = [
    "RESTART",
    "RESTART_UNPLANNED",
    "SHUTDOWN",
    "SHUTDOWN_OR_RESTART_PENDING",
    "AGENT_RESTART",
    "UNEXPECTED_AGENT_RECOVERY",
    "AGENT_STOPPED",
    "SLEEP",
    "NETWORK_UNAVAILABLE",
    "SERVER_UNAVAILABLE",
]


@dataclass(frozen=True)
class ReasonEvidence:
    start: datetime
    end: datetime
    reason: str

    def overlaps(self, seg_start: datetime, seg_end: datetime) -> bool:
        return self.start < seg_end and self.end > seg_start


def _normalize(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Every AgentLifecycleEvent timestamp is written as aware UTC (the
    client is required to send aware datetimes; nothing in this pipeline
    ever treats a naive client-supplied value as local time by
    convention). SQLite strips tzinfo on round-trip regardless -- the
    same well-documented limitation worked around elsewhere in this
    codebase (see MonitoringWindowService, ServerLifecycleEvent) -- so a
    naive value read back here is re-tagged UTC, never local time.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _boottime_changed(a: Optional[datetime], b: Optional[datetime]) -> Optional[bool]:
    """None if either boottime is missing (can't compare); else whether
    the delta exceeds BOOTTIME_TOLERANCE_SECONDS."""
    a, b = _normalize(a), _normalize(b)
    if a is None or b is None:
        return None
    return abs((b - a).total_seconds()) > BOOTTIME_TOLERANCE_SECONDS


def get_reason_evidence(
    db: Session,
    device_id: int,
    window_start: datetime,
    window_end: datetime,
) -> List[ReasonEvidence]:
    """
    Derive every reason-bearing interval overlapping
    [window_start, window_end] for this device, from raw
    AgentLifecycleEvent rows plus (as a fallback only) Phase 3's
    server-outage evidence. Never infers anything from an absence of
    events -- every interval returned here is anchored to at least one
    real, stored event.
    """
    window_start = _normalize(window_start)
    window_end = _normalize(window_end)

    # Look slightly outside the window so a bracket straddling the edge
    # (e.g. AGENT_STARTED just after window_end) is still found for
    # pairing purposes, mirroring server_lifecycle_service's own pattern.
    pad = timedelta(days=1)
    events = AgentLifecycleRepository.get_events_in_window(
        db, device_id, window_start - pad, window_end + pad
    )

    evidence: List[ReasonEvidence] = []
    handled_agent_started_ids = set()

    for idx, ev in enumerate(events):
        ev_time = _normalize(ev.event_time)

        # --- SLEEP -> next WAKE -------------------------------------
        if ev.event_type == "SLEEP":
            wake = next(
                (e for e in events[idx + 1:] if e.event_type == "WAKE"),
                None,
            )
            end = _normalize(wake.event_time) if wake else window_end
            evidence.append(ReasonEvidence(start=ev_time, end=end, reason="SLEEP"))
            continue

        # --- SHUTDOWN_OR_RESTART_IMMINENT -> next AGENT_STARTED -----
        if ev.event_type == "SHUTDOWN_OR_RESTART_IMMINENT":
            resumption = next(
                (e for e in events[idx + 1:] if e.event_type == "AGENT_STARTED"),
                None,
            )

            if resumption is None:
                evidence.append(
                    ReasonEvidence(
                        start=ev_time,
                        end=window_end,
                        reason="SHUTDOWN_OR_RESTART_PENDING",
                    )
                )
                continue

            handled_agent_started_ids.add(resumption.id)

            resumption_time = _normalize(resumption.event_time)
            gap_seconds = (resumption_time - ev_time).total_seconds()
            prior_boottime = _find_prior_boottime(events, idx)
            changed = _boottime_changed(prior_boottime, resumption.boottime)

            if changed is True:
                reason = (
                    "RESTART"
                    if gap_seconds <= RESTART_VS_SHUTDOWN_GAP_SECONDS
                    else "SHUTDOWN"
                )
                evidence.append(
                    ReasonEvidence(start=ev_time, end=resumption_time, reason=reason)
                )
            # changed is False or None (no boottime evidence, or boottime
            # didn't actually change despite the warning): cannot confirm
            # a reboot occurred -- deliberately left unresolved rather
            # than guessing; the segment falls back to the honest
            # MONITORING_GAP default.
            continue

        # --- AGENT_STOPPED -> next AGENT_STARTED (graceful) ---------
        if ev.event_type == "AGENT_STOPPED":
            resumption = next(
                (e for e in events[idx + 1:] if e.event_type == "AGENT_STARTED"),
                None,
            )
            end = _normalize(resumption.event_time) if resumption else window_end
            evidence.append(
                ReasonEvidence(start=ev_time, end=end, reason="AGENT_STOPPED")
            )
            continue

        # --- NETWORK_UNAVAILABLE -> NETWORK_RECOVERED ---------------
        if ev.event_type == "NETWORK_UNAVAILABLE":
            recovered = next(
                (e for e in events[idx + 1:] if e.event_type == "NETWORK_RECOVERED"),
                None,
            )
            end = _normalize(recovered.event_time) if recovered else window_end
            evidence.append(
                ReasonEvidence(start=ev_time, end=end, reason="NETWORK_UNAVAILABLE")
            )
            continue

        # --- SERVER_UNAVAILABLE -> SERVER_RECOVERED -----------------
        if ev.event_type == "SERVER_UNAVAILABLE":
            recovered = next(
                (e for e in events[idx + 1:] if e.event_type == "SERVER_RECOVERED"),
                None,
            )
            end = _normalize(recovered.event_time) if recovered else window_end
            evidence.append(
                ReasonEvidence(start=ev_time, end=end, reason="SERVER_UNAVAILABLE")
            )
            continue

    # --- AGENT_STARTED events not already explained by a preceding
    #     SHUTDOWN_OR_RESTART_IMMINENT: classify via boottime comparison
    #     against this device's own PREVIOUS AGENT_STARTED. -------------
    agent_starts = [e for e in events if e.event_type == "AGENT_STARTED"]
    for i, started in enumerate(agent_starts):
        if started.id in handled_agent_started_ids:
            continue

        prev_started = agent_starts[i - 1] if i > 0 else None
        if prev_started is None:
            # First-ever recorded start for this device -- no prior
            # boottime to compare against, nothing to conclude. Mirrors
            # Phase 3's own "first-ever heartbeat" precedent exactly.
            continue

        started_time = _normalize(started.event_time)
        changed = _boottime_changed(prev_started.boottime, started.boottime)

        if changed is None:
            continue  # insufficient evidence to compare -- stay silent

        if changed:
            evidence.append(
                ReasonEvidence(
                    start=_normalize(prev_started.event_time),
                    end=started_time,
                    reason="RESTART_UNPLANNED",
                )
            )
            continue

        # boottime unchanged: the Mac did not reboot. Was there a
        # graceful AGENT_STOPPED between the two starts?
        had_graceful_stop = any(
            e.event_type == "AGENT_STOPPED"
            and _normalize(prev_started.event_time) < _normalize(e.event_time) < started_time
            for e in events
        )
        reason = "AGENT_RESTART" if had_graceful_stop else "UNEXPECTED_AGENT_RECOVERY"
        evidence.append(
            ReasonEvidence(
                start=_normalize(prev_started.event_time),
                end=started_time,
                reason=reason,
            )
        )

    # --- Fallback only: Phase 3's own server-outage evidence, mapped
    #     exclusively to SERVER_UNAVAILABLE -- never to any device-state
    #     reason. Per the approved spec, server outage must never be
    #     interpreted as shutdown/restart/sleep/agent-stopped. ----------
    for outage in get_outage_evidence(db, window_start, window_end):
        evidence.append(
            ReasonEvidence(start=outage.start, end=outage.end, reason="SERVER_UNAVAILABLE")
        )

    return [e for e in evidence if e.overlaps(window_start, window_end)]


def _find_prior_boottime(events: List[AgentLifecycleEvent], before_idx: int) -> Optional[datetime]:
    """Most recent AGENT_STARTED.boottime among events[:before_idx]."""
    for e in reversed(events[:before_idx]):
        if e.event_type == "AGENT_STARTED" and e.boottime is not None:
            return e.boottime
    return None


def attach_reason(
    segments: List[Dict],
    device_id: int,
    db: Session,
) -> List[Dict]:
    """
    For each gap-type segment (SLEEP_CONFIRMED / MONITORING_GAP /
    OFF_SESSION) in `segments`, set segment["reason"] to the
    highest-priority overlapping ReasonEvidence, or leave it unset
    (defaulting to None on serialization) if none applies.

    ACTIVE/IDLE/NO_SESSION segments are never touched -- `reason` is only
    ever meaningful for a segment that already represents "monitoring
    coverage was a gap and the cause is being explained," never for
    confirmed engagement or the absence of a session entirely.
    """
    gap_types = {"SLEEP_CONFIRMED", "MONITORING_GAP", "OFF_SESSION"}
    gap_segments = [s for s in segments if s.get("type") in gap_types]

    if not gap_segments:
        return segments

    window_start = min(s["start"] for s in gap_segments)
    window_end = max(s["end"] for s in gap_segments)

    evidence = get_reason_evidence(db, device_id, window_start, window_end)
    evidence_by_priority = sorted(
        evidence,
        key=lambda e: _REASON_PRIORITY.index(e.reason)
        if e.reason in _REASON_PRIORITY
        else len(_REASON_PRIORITY),
    )

    for seg in segments:
        if seg.get("type") not in gap_types:
            continue
        match = next(
            (e for e in evidence_by_priority if e.overlaps(seg["start"], seg["end"])),
            None,
        )
        if match is not None:
            seg["reason"] = match.reason

    return segments

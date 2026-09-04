from datetime import datetime
from typing import List, Optional, TypedDict


# Reuses the exact same numeric value as
# MonitoringWindowService.DEFAULT_GAP_THRESHOLD_SECONDS, deliberately, rather
# than introducing a second independent constant. MonitoringWindowService
# uses it to decide "this much silence means the device wasn't observed";
# here it is reused for the logical inverse -- "this much continuous
# presence means the device WAS observed" -- so a monitored run can be
# trusted as real evidence rather than a stray heartbeat or two. See class
# docstring for the full reasoning and the real data this was validated
# against.
SUSTAINED_RUN_SECONDS = 180

# Session-boundary inference ceiling. A gap flanked by CONFIRMED monitored
# evidence on both sides (see SUSTAINED_RUN_SECONDS) is classified
# MONITORING_GAP if its own duration does not exceed this value, or
# OFF_SESSION if it does. Derived from real IXMAC007 data: the largest
# genuine in-session gap observed was ~1827s (30m27s); the smallest gap that
# genuinely represented a boundary between two work periods was ~52510s
# (14h35m). 3600s sits with wide margin inside that empty "dead zone" --
# the exact value is not fragile or load-bearing; see class docstring.
OFF_SESSION_CEILING_SECONDS = 3600


class ClassifiedSegment(TypedDict):
    start: datetime
    end: datetime
    monitored: bool
    # Only present when monitored is False.
    gap_type: Optional[str]


class WorkSessionClassifier:
    """
    Classifies each MonitoringWindowService "not monitored" gap segment as
    exactly one of: SLEEP_CONFIRMED, MONITORING_GAP, or OFF_SESSION.

    IMPORTANT -- what this class deliberately does NOT do:
      - It never reads clock hour, day of week, or any fixed schedule.
        A user working at 2 AM is evaluated by the identical logic as one
        working at 10 AM.
      - It never infers SLEEP_CONFIRMED from gap duration, from the
        absence of application data, or from an interval merely being
        overnight. SLEEP_CONFIRMED requires an explicit sleep/power-state
        signal that the current agent does not send anywhere in its
        payload (verified against AgentHeartbeatRequest and every other
        agent-facing schema) -- see has_confirmed_sleep_evidence() below,
        which is therefore always False today. SLEEP_CONFIRMED is defined
        here as a reachable state in the type system, ready for a future
        agent enhancement, but is never actually produced by the current
        implementation.
      - MONITORING_GAP does NOT mean "confirmed short sleep". It means
        monitoring evidence disappeared for a bounded stretch, flanked by
        real engagement on both sides -- the cause (real sleep, an agent
        hiccup, a network outage, anything else that stops heartbeats) is
        unknown and is not claimed by this label. It must never be
        displayed or treated as confirmed Sleep by any caller.
      - OFF_SESSION is the system's best available INFERENCE that a gap
        represents the boundary between two separate periods of
        engagement -- never a confirmed fact. It is not determined from
        clock time, and is not simply "gap > OFF_SESSION_CEILING_SECONDS"
        in isolation: it also fires whenever the gap lacks confirmed
        evidence on either flanking side, regardless of duration (this is
        exactly what rejects a short, isolated heartbeat/application
        stutter -- e.g. the real DarkWake pattern on IXMAC007 -- from ever
        being treated as a real interruption inside an ongoing session).

    A monitored run shorter than SUSTAINED_RUN_SECONDS is "unconfirmed" --
    a stutter, not reliable evidence of genuine observation -- and is
    absorbed into its adjacent gap rather than being labeled ACTIVE/IDLE on
    its own, and can never itself serve as the "confirmed" evidence a
    neighboring gap needs to become MONITORING_GAP.
    """

    @staticmethod
    def has_confirmed_sleep_evidence(gap_start: datetime, gap_end: datetime) -> bool:
        """
        Extension point for a future agent-provided sleep/power-state
        signal (e.g. pmset-derived wake-reason data attached to a
        heartbeat or a dedicated event). No such signal exists anywhere in
        the current device_heartbeats/applications/idle_events schema or
        agent-facing request payloads -- confirmed by direct inspection of
        AgentHeartbeatRequest and every other agent schema, which carry no
        power-state, wake-reason, or DarkWake indicator field of any kind.

        Deliberately does NOT infer sleep from gap duration, time of day,
        or application-record absence -- per explicit design requirement,
        duration alone must never be treated as proof the device was
        asleep. Always returns False today; this is the honest, correct
        answer given the data that actually exists, not a placeholder bug.
        """
        return False

    @staticmethod
    def classify(raw_segments) -> List[ClassifiedSegment]:
        """
        raw_segments: MonitoringWindowService.get_segments()'s output --
        an ordered list of (start, end, monitored: bool) tuples, evaluated
        over a padded window (see TimelineService.build()), not the
        caller's final display window.

        Returns an ordered list of ClassifiedSegment dicts. Monitored
        segments are passed through with monitored=True and gap_type=None
        (the caller still splits these into ACTIVE/IDLE using idle_events,
        unchanged from before); not-monitored segments are passed through
        with monitored=False and gap_type set to one of "SLEEP_CONFIRMED",
        "MONITORING_GAP", or "OFF_SESSION".
        """
        if not raw_segments:
            return []

        # Pass 1: mark every monitored run confirmed / unconfirmed.
        marked = []
        for start, end, monitored in raw_segments:
            confirmed = bool(monitored) and (end - start).total_seconds() >= SUSTAINED_RUN_SECONDS
            marked.append({"start": start, "end": end, "monitored": bool(monitored), "confirmed": confirmed})

        # Pass 2: coalesce gaps around unconfirmed ("stutter") monitored
        # runs -- an unconfirmed run can never stand as its own segment;
        # it is folded into whichever not-monitored span it's adjacent to.
        merged = []
        for seg in marked:
            is_gap_like = (not seg["monitored"]) or (seg["monitored"] and not seg["confirmed"])
            if is_gap_like:
                if merged and merged[-1]["is_gap_like"]:
                    merged[-1]["end"] = seg["end"]
                else:
                    merged.append({"start": seg["start"], "end": seg["end"], "is_gap_like": True})
            else:
                merged.append({"start": seg["start"], "end": seg["end"], "is_gap_like": False})

        # Pass 3: classify each surviving gap-like span.
        result: List[ClassifiedSegment] = []
        for idx, seg in enumerate(merged):
            if not seg["is_gap_like"]:
                result.append({"start": seg["start"], "end": seg["end"], "monitored": True, "gap_type": None})
                continue

            before = merged[idx - 1] if idx > 0 and not merged[idx - 1]["is_gap_like"] else None
            after = merged[idx + 1] if idx < len(merged) - 1 and not merged[idx + 1]["is_gap_like"] else None
            duration_seconds = (seg["end"] - seg["start"]).total_seconds()

            if WorkSessionClassifier.has_confirmed_sleep_evidence(seg["start"], seg["end"]):
                gap_type = "SLEEP_CONFIRMED"
            elif before is None or after is None:
                gap_type = "OFF_SESSION"
            elif duration_seconds > OFF_SESSION_CEILING_SECONDS:
                gap_type = "OFF_SESSION"
            else:
                gap_type = "MONITORING_GAP"

            result.append({"start": seg["start"], "end": seg["end"], "monitored": False, "gap_type": gap_type})

        return result

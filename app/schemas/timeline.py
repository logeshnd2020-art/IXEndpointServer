from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class TimelineSegment(BaseModel):
    start: datetime
    end: datetime
    # SLEEP_CONFIRMED: an explicit sleep/power-state signal established
    # this interval as genuine sleep. No such signal exists in the current
    # agent payload/schema, so this state is never actually produced today
    # -- see WorkSessionClassifier.has_confirmed_sleep_evidence().
    #
    # MONITORING_GAP: monitoring evidence (heartbeats) disappeared for a
    # bounded stretch, flanked by confirmed engagement on both sides. The
    # cause is unknown -- could be real sleep, could be the agent failing
    # while the device stayed awake -- and is NOT claimed by this label.
    # Must never be displayed or treated as confirmed Sleep.
    #
    # OFF_SESSION: the system's best available inference, from heartbeat
    # evidence alone, that this stretch represents the boundary between
    # two separate periods of engagement rather than a single continuous
    # interruption -- never a confirmed fact, and never determined from
    # clock time, day of week, or a fixed schedule. See
    # WorkSessionClassifier for the exact evidence-based rule.
    #
    # NO_SESSION means no session was open at all during this stretch
    # (only used by the day-scoped timeline, e.g. before login/after
    # logout) -- distinct from the three gap types above, all of which
    # mean a session *was* open but not observed.
    type: Literal["ACTIVE", "IDLE", "SLEEP_CONFIRMED", "MONITORING_GAP", "OFF_SESSION", "NO_SESSION"]
    duration_seconds: int


class TimelineResponse(BaseModel):
    device_id: int
    hostname: str
    # Populated for the single-session view (?session_id= or default
    # active/most-recent session); left unset for the day-scoped view
    # (?date=), which can span multiple sessions.
    session_id: Optional[int] = None
    session_status: Optional[str] = None
    date: Optional[str] = None
    window_start: datetime
    window_end: datetime
    segments: List[TimelineSegment]

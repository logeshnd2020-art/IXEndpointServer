from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class TimelineSegment(BaseModel):
    start: datetime
    end: datetime
    # SLEEP_GAP covers both confirmed macOS sleep and any other unobserved
    # monitoring gap (e.g. agent not running) -- the heartbeat stream
    # cannot distinguish the two, so both are reported honestly under one
    # label rather than a fabricated split. See MonitoringWindowService.
    # NO_SESSION means no session was open at all during this stretch
    # (only used by the day-scoped timeline, e.g. before login/after
    # logout) -- distinct from SLEEP_GAP, which means a session *was*
    # open but not observed.
    type: Literal["ACTIVE", "IDLE", "SLEEP_GAP", "NO_SESSION"]
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

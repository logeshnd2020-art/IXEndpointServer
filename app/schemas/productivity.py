from typing import List

from pydantic import BaseModel


class ApplicationUsageResponse(BaseModel):

    application: str

    elapsed_seconds: int

    idle_seconds: int

    active_seconds: int


class ProductivityResponse(BaseModel):

    hostname: str

    username: str

    working_seconds: int

    idle_seconds: int

    active_seconds: int

    # SLEEP_CONFIRMED total only -- genuine sleep/power-state evidence.
    # Always 0 today: no current agent version sends a signal that could
    # establish confirmed sleep. See WorkSessionClassifier.
    sleep_seconds: int

    # Monitoring evidence (heartbeats) disappeared for a bounded stretch
    # inside an otherwise-confirmed session; cause unknown (could be real
    # sleep, could be an agent/network hiccup while awake) and not claimed
    # by this figure. Must never be displayed or treated as confirmed
    # Sleep.
    monitoring_gap_seconds: int

    # The system's best-available inference (from heartbeat evidence
    # alone, never from clock time) that this time represents a boundary
    # between two separate periods of engagement -- never a confirmed
    # fact. Excluded from working_seconds/productivity_percent.
    off_session_seconds: int

    productivity_percent: float

    mouse_clicks: int

    keyboard_hits: int

    applications: List[ApplicationUsageResponse]

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel


class ApplicationInterval(BaseModel):
    """
    One attributable (ACTIVE or IDLE) overlap between an application usage
    record and the canonical segment list. Never produced for any overlap
    with SLEEP_CONFIRMED, MONITORING_GAP, OFF_SESSION, or NO_SESSION -- an
    application record whose entire span falls inside one of those simply
    contributes no intervals at all, rather than a zero-duration or
    mislabeled one. See app.services.timeline_service.TimelineService and
    the /api/device/{device_id}/applications handler.
    """

    start: datetime
    end: datetime
    status: Literal["ACTIVE", "IDLE"]
    duration_seconds: int


class ApplicationUsageDetail(BaseModel):
    application: str
    active_seconds: int
    idle_seconds: int
    total_seconds: int
    intervals: List[ApplicationInterval]


class ApplicationDrilldownResponse(BaseModel):
    device_id: int
    hostname: str
    date: str
    applications: List[ApplicationUsageDetail]

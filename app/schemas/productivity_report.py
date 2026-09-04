from typing import List
from pydantic import BaseModel


class ApplicationReport(BaseModel):
    application: str
    elapsed_seconds: int
    idle_seconds: int
    active_seconds: int


class ProductivityReport(BaseModel):
    hostname: str
    username: str
    period_start: str
    period_end: str
    working_seconds: int
    idle_seconds: int
    active_seconds: int
    # SLEEP_CONFIRMED total only -- always 0 today; see ProductivityService
    # for why this is deliberately not "every kind of unobserved time".
    sleep_seconds: int
    # Cause-unknown monitoring evidence gap inside an otherwise-confirmed
    # session -- never displayed/treated as confirmed Sleep.
    monitoring_gap_seconds: int
    # Best-available inference of a boundary between two engagement
    # periods -- never a confirmed fact, never clock-based.
    off_session_seconds: int
    productivity_percent: float
    applications: List[ApplicationReport]


class ProductivityReportResponse(BaseModel):
    report_type: str
    reports: List[ProductivityReport]

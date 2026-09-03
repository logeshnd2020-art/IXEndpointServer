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
    sleep_seconds: int
    productivity_percent: float
    applications: List[ApplicationReport]


class ProductivityReportResponse(BaseModel):
    report_type: str
    reports: List[ProductivityReport]

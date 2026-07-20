from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApplicationStartRequest(BaseModel):
    serial_number: str
    application_name: str
    window_title: Optional[str] = None


class ApplicationStopRequest(BaseModel):
    serial_number: str


class ApplicationResponse(BaseModel):
    application_id: int
    application_name: str
    start_time: datetime

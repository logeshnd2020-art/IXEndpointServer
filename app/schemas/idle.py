from datetime import datetime

from pydantic import BaseModel


class IdleStartRequest(BaseModel):
    serial_number: str


class IdleEndRequest(BaseModel):
    serial_number: str


class IdleResponse(BaseModel):
    idle_id: int
    idle_start: datetime

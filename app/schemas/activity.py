from datetime import datetime

from pydantic import BaseModel


class ActivityRequest(BaseModel):
    serial_number: str
    mouse_clicks: int
    keyboard_hits: int


class ActivityResponse(BaseModel):
    activity_id: int
    captured_at: datetime

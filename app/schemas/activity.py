from datetime import datetime

from pydantic import BaseModel, Field


class ActivityRequest(BaseModel):
    serial_number: str
    mouse_clicks: int = Field(ge=0)
    keyboard_hits: int = Field(ge=0)


class ActivityResponse(BaseModel):
    activity_id: int
    captured_at: datetime

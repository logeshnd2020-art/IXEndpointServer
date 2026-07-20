from datetime import datetime
from pydantic import BaseModel


class CurrentApplicationResponse(BaseModel):
    hostname: str
    username: str
    application: str
    window_title: str
    started_at: datetime

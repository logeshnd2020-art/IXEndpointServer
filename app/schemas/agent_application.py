from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentApplicationSyncRequest(BaseModel):
    local_application_id: int
    local_session_id: int

    application_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    window_title: Optional[str] = None

    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None


class AgentApplicationSyncResponse(BaseModel):
    status: str
    server_application_id: int
    local_application_id: int
    server_session_id: int
    local_session_id: int
    created: bool

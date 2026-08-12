from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentSessionSyncRequest(BaseModel):
    local_session_id: int
    username: str = Field(..., min_length=1, max_length=100)
    login_time: datetime
    logout_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None


class AgentSessionSyncResponse(BaseModel):
    status: str
    server_session_id: int
    local_session_id: int
    session_status: str
    created: bool

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentIdleSyncRequest(BaseModel):
    local_idle_id: int
    local_session_id: int

    idle_start: datetime
    idle_end: Optional[datetime] = None
    idle_seconds: Optional[int] = Field(default=None, ge=0)


class AgentIdleSyncResponse(BaseModel):
    status: str
    server_idle_id: int
    local_idle_id: int
    server_session_id: int
    local_session_id: int
    created: bool

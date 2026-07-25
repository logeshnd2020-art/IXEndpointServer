from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AgentHeartbeatRequest(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    battery_level: int
    logged_in_user: Optional[str] = None
    hostname: str
    ip_address: str
    network_name: Optional[str] = None
    agent_version: str
    uptime_seconds: int


class AgentHeartbeatResponse(BaseModel):
    status: str
    server_time: datetime
    heartbeat_interval: int
    commands: list

    model_config = ConfigDict(from_attributes=True)

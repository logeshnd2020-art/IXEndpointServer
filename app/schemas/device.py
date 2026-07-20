from typing import Optional

from pydantic import BaseModel, ConfigDict


class DeviceRegister(BaseModel):
    hostname: str
    serial_number: str
    username: str

    macos_version: Optional[str] = None
    device_model: Optional[str] = None
    agent_version: Optional[str] = None
    ip_address: Optional[str] = None


class DeviceResponse(BaseModel):
    device_id: int
    status: str

    model_config = ConfigDict(from_attributes=True)
class HeartbeatRequest(BaseModel):
    serial_number: str
    ip_address: str
    agent_version: str


class HeartbeatResponse(BaseModel):
    status: str
    last_seen: str

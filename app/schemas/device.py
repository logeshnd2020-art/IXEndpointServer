from datetime import datetime
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


class AgentRegisterRequest(BaseModel):
    enrollment_key: str
    device_uuid: str
    serial_number: str
    hostname: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    processor: Optional[str] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    agent_version: Optional[str] = None


class AgentRegisterResponse(BaseModel):
    device_id: int
    device_token: str
    heartbeat_interval: int


class DeviceCreateRequest(BaseModel):
    device_uuid: str
    hostname: str
    serial_number: str
    username: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    processor: Optional[str] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    agent_version: Optional[str] = None


class DeviceUpdateRequest(BaseModel):
    hostname: Optional[str] = None
    os_version: Optional[str] = None
    agent_version: Optional[str] = None
    processor: Optional[str] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    status: Optional[str] = None
    last_seen: Optional[datetime] = None


class DeviceDetailResponse(BaseModel):
    id: int
    device_uuid: Optional[str] = None
    hostname: str
    serial_number: str
    username: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    processor: Optional[str] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    status: Optional[str] = None
    agent_version: Optional[str] = None
    registration_date: Optional[datetime] = None
    is_registered: bool
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class HeartbeatRequest(BaseModel):
    serial_number: str
    ip_address: str
    agent_version: str


class HeartbeatResponse(BaseModel):
    status: str
    last_seen: str

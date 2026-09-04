from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeviceMonitorDetailResponse(BaseModel):
    device_id: int
    hostname: str
    username: str
    status: str
    ip_address: Optional[str] = None
    last_seen: Optional[datetime] = None
    serial_number: Optional[str] = None
    device_uuid: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    processor: Optional[str] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    agent_version: Optional[str] = None
    is_registered: bool = False
    registration_date: Optional[datetime] = None


class InstalledApplicationDetail(BaseModel):
    name: str
    version: Optional[str] = None
    bundle_id: Optional[str] = None
    install_path: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

from datetime import datetime

from pydantic import BaseModel


class LiveDeviceResponse(BaseModel):
    hostname: str
    serial_number: str
    username: str
    status: str
    ip_address: str
    last_seen: datetime

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LiveDeviceResponse(BaseModel):

    device_id: int

    hostname: str

    serial_number: str

    username: str

    status: str

    ip_address: str

    last_seen: Optional[datetime] = None

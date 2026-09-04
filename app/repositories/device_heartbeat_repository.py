from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.device_heartbeat import DeviceHeartbeat


class DeviceHeartbeatRepository:

    @staticmethod
    def create_heartbeat(
        db: Session,
        device: Device,
        cpu_usage: float,
        memory_usage: float,
        disk_usage: float,
        battery_level: int,
        logged_in_user: Optional[str],
        ip_address: str,
        network_name: Optional[str],
        uptime_seconds: int,
        mac_address: Optional[str] = None,
    ) -> DeviceHeartbeat:
        heartbeat = DeviceHeartbeat(
            device=device,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            battery_level=battery_level,
            logged_in_user=logged_in_user,
            ip_address=ip_address,
            network_name=network_name,
            mac_address=mac_address,
            uptime_seconds=uptime_seconds,
            timestamp=datetime.now(),
        )
        db.add(heartbeat)
        db.commit()
        db.refresh(heartbeat)
        return heartbeat

    @staticmethod
    def get_latest_heartbeat(db: Session, device_id: int) -> Optional[DeviceHeartbeat]:
        return (
            db.query(DeviceHeartbeat)
            .filter(DeviceHeartbeat.device_id == device_id)
            .order_by(DeviceHeartbeat.timestamp.desc())
            .first()
        )

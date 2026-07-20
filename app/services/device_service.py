from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.exceptions.device import DeviceNotFound
from app.models.device import Device
from app.repositories.device_repository import DeviceRepository
from app.schemas.device import DeviceRegister, HeartbeatRequest


class DeviceService:

    @staticmethod
    def register(db: Session, request: DeviceRegister):

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number
        )

        if device:
            device.hostname = request.hostname
            device.username = request.username
            device.macos_version = request.macos_version
            device.device_model = request.device_model
            device.agent_version = request.agent_version
            device.ip_address = request.ip_address
            device.last_seen = datetime.now(timezone.utc)
            device.is_online = True

            return DeviceRepository.update(db, device)

        device = Device(
            hostname=request.hostname,
            serial_number=request.serial_number,
            username=request.username,
            macos_version=request.macos_version,
            device_model=request.device_model,
            agent_version=request.agent_version,
            ip_address=request.ip_address,
            is_online=True,
            last_seen=datetime.now(timezone.utc),
        )

        return DeviceRepository.create(db, device)

    @staticmethod
    def heartbeat(db: Session, request: HeartbeatRequest):

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number
        )

        if not device:
            raise DeviceNotFound()

        device.last_seen = datetime.now(timezone.utc)
        device.ip_address = request.ip_address
        device.agent_version = request.agent_version
        device.is_online = True

        return DeviceRepository.update(db, device)

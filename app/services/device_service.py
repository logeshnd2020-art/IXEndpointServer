from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.exceptions.device import DeviceNotFound, DeviceAlreadyExists
from app.models.device import Device
from app.repositories.device_repository import DeviceRepository
from app.schemas.device import (
    DeviceRegister,
    HeartbeatRequest,
    DeviceCreateRequest,
    DeviceUpdateRequest,
)


class DeviceService:

    @staticmethod
    def create_device(db: Session, request: DeviceCreateRequest) -> Device:
        if DeviceRepository.get_device_by_serial(db, request.serial_number):
            raise DeviceAlreadyExists("serial_number already exists")

        if DeviceRepository.get_device_by_uuid(db, request.device_uuid):
            raise DeviceAlreadyExists("device_uuid already exists")

        now = datetime.now(timezone.utc)
        device = Device(
            device_uuid=request.device_uuid,
            hostname=request.hostname,
            serial_number=request.serial_number,
            username=request.username,
            manufacturer=request.manufacturer,
            model=request.model,
            platform=request.platform,
            os_name=request.os_name,
            os_version=request.os_version,
            processor=request.processor,
            memory_gb=request.memory_gb,
            storage_gb=request.storage_gb,
            agent_version=request.agent_version,
            status="registered",
            registration_date=now,
            is_registered=True,
            created_at=now,
            updated_at=now,
            is_online=False,
            last_seen=None,
        )

        return DeviceRepository.create_device(db, device)

    @staticmethod
    def get_device(db: Session, device_id: int) -> Device:
        device = DeviceRepository.get_device_by_id(db, device_id)
        if not device:
            raise DeviceNotFound()
        return device

    @staticmethod
    def list_devices(db: Session) -> List[Device]:
        return DeviceRepository.list_devices(db)

    @staticmethod
    def update_device(db: Session, device_id: int, request: DeviceUpdateRequest) -> Device:
        device = DeviceRepository.get_device_by_id(db, device_id)
        if not device:
            raise DeviceNotFound()

        if request.hostname is not None:
            device.hostname = request.hostname
        if request.os_version is not None:
            device.os_version = request.os_version
        if request.agent_version is not None:
            device.agent_version = request.agent_version
        if request.processor is not None:
            device.processor = request.processor
        if request.memory_gb is not None:
            device.memory_gb = request.memory_gb
        if request.storage_gb is not None:
            device.storage_gb = request.storage_gb
        if request.status is not None:
            device.status = request.status
        if request.last_seen is not None:
            device.last_seen = request.last_seen

        device.updated_at = datetime.now(timezone.utc)

        return DeviceRepository.update_device(db, device)

    @staticmethod
    def delete_device(db: Session, device_id: int) -> None:
        device = DeviceRepository.get_device_by_id(db, device_id)
        if not device:
            raise DeviceNotFound()

        DeviceRepository.delete_device(db, device)

    @staticmethod
    def register(db: Session, request: DeviceRegister) -> Device:
        now = datetime.now(timezone.utc)
        device = DeviceRepository.get_device_by_serial(
            db,
            request.serial_number,
        )

        if device:
            device.hostname = request.hostname
            device.username = request.username
            device.macos_version = request.macos_version
            device.device_model = request.device_model
            device.agent_version = request.agent_version
            device.ip_address = request.ip_address
            device.last_seen = now
            device.is_online = True
            device.is_registered = True
            device.status = "registered"
            if not device.registration_date:
                device.registration_date = now

            return DeviceRepository.update_device(db, device)

        device = Device(
            device_uuid=None,
            hostname=request.hostname,
            serial_number=request.serial_number,
            username=request.username,
            macos_version=request.macos_version,
            device_model=request.device_model,
            agent_version=request.agent_version,
            ip_address=request.ip_address,
            is_online=True,
            last_seen=now,
            is_registered=True,
            status="registered",
            registration_date=now,
            created_at=now,
            updated_at=now,
        )

        return DeviceRepository.create_device(db, device)

    @staticmethod
    def heartbeat(db: Session, request: HeartbeatRequest) -> Device:
        device = DeviceRepository.get_device_by_serial(
            db,
            request.serial_number,
        )

        if not device:
            raise DeviceNotFound()

        device.last_seen = datetime.now(timezone.utc)
        device.ip_address = request.ip_address
        device.agent_version = request.agent_version
        device.is_online = True

        return DeviceRepository.update_device(db, device)

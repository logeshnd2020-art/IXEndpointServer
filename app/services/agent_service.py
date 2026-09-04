import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_value
from app.exceptions.device import DeviceAlreadyExists
from app.models.device import Device
from app.repositories.device_repository import DeviceRepository
from app.repositories.device_heartbeat_repository import DeviceHeartbeatRepository
from app.services.enrollment_key_service import EnrollmentKeyService
from app.schemas.device import AgentRegisterRequest, AgentRegisterResponse
from app.schemas.heartbeat import AgentHeartbeatRequest, AgentHeartbeatResponse


class AgentService:
    HEARTBEAT_INTERVAL = 300

    @staticmethod
    def _apply_registration_fields(
        device: Device,
        request: AgentRegisterRequest,
        now: datetime,
    ) -> None:
        """Apply common registration fields to a device."""
        device.device_uuid = request.device_uuid
        device.hostname = request.hostname
        device.serial_number = request.serial_number
        device.username = request.device_uuid
        device.manufacturer = request.manufacturer
        device.model = request.model
        device.platform = request.platform
        device.os_name = request.os_name
        device.os_version = request.os_version
        device.processor = request.processor
        device.memory_gb = request.memory_gb
        device.storage_gb = request.storage_gb
        device.agent_version = request.agent_version
        device.status = "registered"

        if not device.registration_date:
            device.registration_date = now

        device.is_registered = True
        device.updated_at = now
        device.last_seen = now

    @staticmethod
    def register_agent(
        db: Session,
        request: AgentRegisterRequest,
    ) -> AgentRegisterResponse:

        enrollment_key = EnrollmentKeyService.validate_key(
            db,
            request.enrollment_key,
        )

        if not enrollment_key:
            raise PermissionError("Invalid enrollment key")

        now = datetime.now(timezone.utc)

        existing_by_uuid = DeviceRepository.get_device_by_uuid(
            db,
            request.device_uuid,
        )

        existing_by_serial = DeviceRepository.get_device_by_serial(
            db,
            request.serial_number,
        )

        if (
            existing_by_uuid
            and existing_by_serial
            and existing_by_uuid.id != existing_by_serial.id
        ):
            raise DeviceAlreadyExists(
                "Device UUID and serial number conflict"
            )

        device = existing_by_uuid or existing_by_serial

        new_registration = False
        is_new = device is None

        if device:
            if (
                device.device_uuid
                and device.device_uuid != request.device_uuid
            ):
                raise DeviceAlreadyExists("Device UUID conflict")

            if (
                device.serial_number
                and device.serial_number != request.serial_number
            ):
                raise DeviceAlreadyExists("Serial number conflict")

            if not device.is_registered:
                new_registration = True

            AgentService._apply_registration_fields(
                device,
                request,
                now,
            )

        else:
            new_registration = True

            device = Device()

            AgentService._apply_registration_fields(
                device,
                request,
                now,
            )

            device.is_online = True
            device.created_at = now

        # Generate a new device authentication token.
        raw_token = secrets.token_urlsafe(32)

        device.device_token_hash = hash_value(raw_token)
        device.token_created_at = now
        device.token_last_used = now

        if is_new:
            device = DeviceRepository.create_device(db, device)
        else:
            device = DeviceRepository.update_device(db, device)

        if new_registration:
            EnrollmentKeyService.increment_registered_count(
                db,
                enrollment_key,
            )

        return AgentRegisterResponse(
            device_id=device.id,
            device_token=raw_token,
            heartbeat_interval=AgentService.HEARTBEAT_INTERVAL,
        )

    @staticmethod
    def heartbeat(
        db: Session,
        request: AgentHeartbeatRequest,
        device: Device,
    ) -> AgentHeartbeatResponse:

        now = datetime.now(timezone.utc)

        device.last_seen = now
        device.token_last_used = now
        device.agent_version = request.agent_version
        device.status = "Online"
        device.is_online = True

        device = DeviceRepository.update_device(
            db,
            device,
        )

        DeviceHeartbeatRepository.create_heartbeat(
            db=db,
            device=device,
            cpu_usage=request.cpu_usage,
            memory_usage=request.memory_usage,
            disk_usage=request.disk_usage,
            battery_level=request.battery_level,
            logged_in_user=request.logged_in_user,
            ip_address=request.ip_address,
            network_name=request.network_name,
            mac_address=request.mac_address,
            uptime_seconds=request.uptime_seconds,
        )

        return AgentHeartbeatResponse(
            status="success",
            server_time=datetime.now(timezone.utc),
            heartbeat_interval=AgentService.HEARTBEAT_INTERVAL,
            commands=[],
        )

    @staticmethod
    def update_inventory(
        db: Session,
        request,
        device: Device,
    ) -> Device:
        """
        Update inventory information for an authenticated device.

        Device identity is determined by the Device authentication
        token rather than data supplied by the client.
        """

        if request.hostname is not None:
            device.hostname = request.hostname

        if request.manufacturer is not None:
            device.manufacturer = request.manufacturer

        if request.model is not None:
            device.model = request.model
            device.device_model = request.model

        if request.platform is not None:
            device.platform = request.platform

        if request.os_name is not None:
            device.os_name = request.os_name

        if request.os_version is not None:
            device.os_version = request.os_version
            device.macos_version = request.os_version

        if request.processor is not None:
            device.processor = request.processor

        if request.memory_gb is not None:
            device.memory_gb = request.memory_gb

        if request.storage_gb is not None:
            device.storage_gb = request.storage_gb

        if request.agent_version is not None:
            device.agent_version = request.agent_version

        if request.ip_address is not None:
            device.ip_address = request.ip_address

        device.updated_at = datetime.now(timezone.utc)

        return DeviceRepository.update_device(
            db,
            device,
        )

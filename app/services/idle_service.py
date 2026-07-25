from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions.device import DeviceNotFound, SessionNotFound
from app.models.idle import IdleEvent
from app.repositories.device_repository import DeviceRepository
from app.repositories.idle_repository import IdleRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.idle import IdleEndRequest, IdleStartRequest
from app.utils.datetime import elapsed_seconds


class IdleService:

    @staticmethod
    def start(db: Session, request: IdleStartRequest) -> IdleEvent:

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number,
        )

        if not device:
            raise DeviceNotFound()

        session = SessionRepository.get_active(
            db,
            device.id,
        )

        if not session:
            raise SessionNotFound()

        current = IdleRepository.get_active(
            db,
            session.id,
        )

        if current:
            return current

        idle = IdleEvent(
            device_id=device.id,
            session_id=session.id,
            idle_start=datetime.now(timezone.utc),
        )

        return IdleRepository.create(
            db,
            idle,
        )

    @staticmethod
    def end(db: Session, request: IdleEndRequest) -> Optional[IdleEvent]:

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number,
        )

        if not device:
            raise DeviceNotFound()

        session = SessionRepository.get_active(
            db,
            device.id,
        )

        if not session:
            raise SessionNotFound()

        idle = IdleRepository.get_active(
            db,
            session.id,
        )

        if not idle:
            return None

        idle.idle_end = datetime.now(timezone.utc)

        idle.idle_seconds = elapsed_seconds(idle.idle_start, idle.idle_end)

        return IdleRepository.update(
            db,
            idle,
        )

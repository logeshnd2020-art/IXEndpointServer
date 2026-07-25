from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions.device import DeviceNotFound, SessionNotFound
from app.models.application import Application
from app.repositories.application_repository import ApplicationRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.application import ApplicationStartRequest, ApplicationStopRequest
from app.utils.datetime import elapsed_seconds


class ApplicationService:

    @staticmethod
    def start(db: Session, request: ApplicationStartRequest) -> Application:

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

        current = ApplicationRepository.get_active(
            db,
            session.id,
        )

        now = datetime.now(timezone.utc)

        app = Application(
            device_id=device.id,
            session_id=session.id,
            application_name=request.application_name,
            window_title=request.window_title,
            start_time=now,
        )

        return ApplicationRepository.replace_active(db, current, app, now)

    @staticmethod
    def stop(db: Session, request: ApplicationStopRequest) -> Optional[Application]:

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

        current = ApplicationRepository.get_active(
            db,
            session.id,
        )

        if not current:
            return None

        current.end_time = datetime.now(timezone.utc)

        current.duration_seconds = elapsed_seconds(current.start_time, current.end_time)

        return ApplicationRepository.update(
            db,
            current,
        )

from datetime import datetime, timezone

from app.models.application import Application
from app.repositories.application_repository import ApplicationRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.session_repository import SessionRepository


class ApplicationService:

    @staticmethod
    def start(db, request):

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number,
        )

        session = SessionRepository.get_active(
            db,
            device.id,
        )

        current = ApplicationRepository.get_active(
            db,
            session.id,
        )

        if current:
            current.end_time = datetime.now(timezone.utc)
            current.duration_seconds = int(
                (
                    current.end_time -
                    current.start_time
                ).total_seconds()
            )

            ApplicationRepository.update(db, current)

        app = Application(
            device_id=device.id,
            session_id=session.id,
            application_name=request.application_name,
            window_title=request.window_title,
            start_time=datetime.now(timezone.utc),
        )

        return ApplicationRepository.create(db, app)

    @staticmethod
    def stop(db, request):

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number,
        )

        session = SessionRepository.get_active(
            db,
            device.id,
        )

        current = ApplicationRepository.get_active(
            db,
            session.id,
        )

        if not current:
            return None

        current.end_time = datetime.now(timezone.utc)

        current.duration_seconds = int(
            (
                current.end_time -
                current.start_time
            ).total_seconds()
        )

        return ApplicationRepository.update(
            db,
            current,
        )

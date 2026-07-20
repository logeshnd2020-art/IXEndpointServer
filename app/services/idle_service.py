from datetime import datetime, timezone

from app.models.idle import IdleEvent
from app.repositories.device_repository import DeviceRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.idle_repository import IdleRepository


class IdleService:

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
    def end(db, request):

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number,
        )

        session = SessionRepository.get_active(
            db,
            device.id,
        )

        idle = IdleRepository.get_active(
            db,
            session.id,
        )

        if not idle:
            return None

        idle.idle_end = datetime.now(timezone.utc)

        idle.idle_seconds = int(
            (
                idle.idle_end -
                idle.idle_start
            ).total_seconds()
        )

        return IdleRepository.update(
            db,
            idle,
        )

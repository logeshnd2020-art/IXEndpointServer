from sqlalchemy.orm import Session

from app.exceptions.device import DeviceNotFound, SessionNotFound
from app.models.activity import ActivityEvent
from app.repositories.activity_repository import ActivityRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.activity import ActivityRequest


class ActivityService:

    @staticmethod
    def create(db: Session, request: ActivityRequest) -> ActivityEvent:

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

        activity = ActivityEvent(
            device_id=device.id,
            session_id=session.id,
            mouse_clicks=request.mouse_clicks,
            keyboard_hits=request.keyboard_hits,
        )

        return ActivityRepository.create(
            db,
            activity,
        )

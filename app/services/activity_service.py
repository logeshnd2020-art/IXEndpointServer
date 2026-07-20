from app.models.activity import ActivityEvent
from app.repositories.activity_repository import ActivityRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.session_repository import SessionRepository


class ActivityService:

    @staticmethod
    def create(db, request):

        device = DeviceRepository.get_by_serial(
            db,
            request.serial_number,
        )

        session = SessionRepository.get_active(
            db,
            device.id,
        )

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

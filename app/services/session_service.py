from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.exceptions.device import DeviceNotFound
from app.models.session import Session as UserSession
from app.repositories.device_repository import DeviceRepository
from app.repositories.session_repository import SessionRepository


class SessionService:

    @staticmethod
    def login(db: Session, serial_number: str, username: str):

        device = DeviceRepository.get_by_serial(db, serial_number)

        if not device:
            raise DeviceNotFound()

        active = SessionRepository.get_active(db, device.id)

        if active:
            return active

        session = UserSession(
            device_id=device.id,
            username=username,
            login_time=datetime.now(timezone.utc),
            status="ACTIVE",
        )

        return SessionRepository.create(db, session)

    @staticmethod
    def logout(db: Session, serial_number: str):

        device = DeviceRepository.get_by_serial(db, serial_number)

        if not device:
            raise DeviceNotFound()

        session = SessionRepository.get_active(db, device.id)

        if not session:
            return None

        session.logout_time = datetime.now(timezone.utc)
        session.status = "LOGOUT"

        return SessionRepository.update(db, session)

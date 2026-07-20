from sqlalchemy.orm import Session

from app.models.session import Session as UserSession


class SessionRepository:

    @staticmethod
    def create(db: Session, session: UserSession):
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def update(db: Session, session: UserSession):
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_active(db: Session, device_id: int):
        return (
            db.query(UserSession)
            .filter(
                UserSession.device_id == device_id,
                UserSession.status == "ACTIVE",
            )
            .first()
        )

    @staticmethod
    def get_by_id(db: Session, session_id: int):
        return (
            db.query(UserSession)
            .filter(UserSession.id == session_id)
            .first()
        )

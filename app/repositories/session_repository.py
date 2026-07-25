from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.session import Session as UserSession


class SessionRepository:

    @staticmethod
    def create(db: Session, session: UserSession) -> UserSession:
        db.add(session)
        return SessionRepository._commit_and_refresh(db, session)

    @staticmethod
    def update(db: Session, session: UserSession) -> UserSession:
        return SessionRepository._commit_and_refresh(db, session)

    @staticmethod
    def get_active(db: Session, device_id: int) -> Optional[UserSession]:
        return (
            db.query(UserSession)
            .filter(
                UserSession.device_id == device_id,
                UserSession.status == "ACTIVE",
            )
            .order_by(UserSession.login_time.desc())
            .first()
        )

    @staticmethod
    def get_by_id(db: Session, session_id: int) -> Optional[UserSession]:
        return (
            db.query(UserSession)
            .filter(UserSession.id == session_id)
            .first()
        )

    @staticmethod
    def _commit_and_refresh(db: Session, session: UserSession) -> UserSession:
        try:
            db.commit()
            db.refresh(session)
        except SQLAlchemyError:
            db.rollback()
            raise
        return session

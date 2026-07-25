from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.idle import IdleEvent


class IdleRepository:

    @staticmethod
    def create(db: Session, idle: IdleEvent) -> IdleEvent:
        db.add(idle)
        return IdleRepository._commit_and_refresh(db, idle)

    @staticmethod
    def update(db: Session, idle: IdleEvent) -> IdleEvent:
        return IdleRepository._commit_and_refresh(db, idle)

    @staticmethod
    def get_active(db: Session, session_id: int) -> Optional[IdleEvent]:
        return (
            db.query(IdleEvent)
            .filter(
                IdleEvent.session_id == session_id,
                IdleEvent.idle_end.is_(None),
            )
            .order_by(IdleEvent.idle_start.desc())
            .first()
        )

    @staticmethod
    def _commit_and_refresh(db: Session, idle: IdleEvent) -> IdleEvent:
        try:
            db.commit()
            db.refresh(idle)
        except SQLAlchemyError:
            db.rollback()
            raise
        return idle

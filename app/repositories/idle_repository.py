from sqlalchemy.orm import Session

from app.models.idle import IdleEvent


class IdleRepository:

    @staticmethod
    def create(db: Session, idle: IdleEvent):
        db.add(idle)
        db.commit()
        db.refresh(idle)
        return idle

    @staticmethod
    def update(db: Session, idle: IdleEvent):
        db.commit()
        db.refresh(idle)
        return idle

    @staticmethod
    def get_active(db: Session, session_id: int):
        return (
            db.query(IdleEvent)
            .filter(
                IdleEvent.session_id == session_id,
                IdleEvent.idle_end.is_(None),
            )
            .first()
        )

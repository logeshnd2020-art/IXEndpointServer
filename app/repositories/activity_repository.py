from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent


class ActivityRepository:

    @staticmethod
    def create(db: Session, activity: ActivityEvent) -> ActivityEvent:
        db.add(activity)
        try:
            db.commit()
            db.refresh(activity)
        except SQLAlchemyError:
            db.rollback()
            raise
        return activity

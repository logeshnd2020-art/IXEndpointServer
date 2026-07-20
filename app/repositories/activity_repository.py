from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent


class ActivityRepository:

    @staticmethod
    def create(db: Session, activity: ActivityEvent):
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity

from sqlalchemy.orm import Session

from app.models.application import Application


class ApplicationRepository:

    @staticmethod
    def create(db: Session, app: Application):
        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    @staticmethod
    def update(db: Session, app: Application):
        db.commit()
        db.refresh(app)
        return app

    @staticmethod
    def get_active(db: Session, session_id: int):
        return (
            db.query(Application)
            .filter(
                Application.session_id == session_id,
                Application.end_time.is_(None),
            )
            .first()
        )

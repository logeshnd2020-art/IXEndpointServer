from datetime import datetime
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.application import Application
from app.utils.datetime import elapsed_seconds


class ApplicationRepository:

    @staticmethod
    def create(
        db: Session,
        app: Application,
    ) -> Application:

        db.add(app)

        return ApplicationRepository._commit_and_refresh(
            db,
            app,
        )

    @staticmethod
    def update(
        db: Session,
        app: Application,
    ) -> Application:

        return ApplicationRepository._commit_and_refresh(
            db,
            app,
        )

    @staticmethod
    def get_active(
        db: Session,
        session_id: int,
    ) -> Optional[Application]:

        return (
            db.query(Application)
            .filter(
                Application.session_id == session_id,
                Application.end_time.is_(None),
            )
            .order_by(Application.start_time.desc())
            .first()
        )

    @staticmethod
    def get_by_local_application_id(
        db: Session,
        device_id: int,
        local_application_id: int,
    ) -> Optional[Application]:

        return (
            db.query(Application)
            .filter(
                Application.device_id == device_id,
                Application.local_application_id == local_application_id,
            )
            .first()
        )

    @staticmethod
    def replace_active(
        db: Session,
        current: Optional[Application],
        app: Application,
        ended_at: datetime,
    ) -> Application:

        if current is not None:
            current.end_time = ended_at
            current.duration_seconds = elapsed_seconds(
                current.start_time,
                ended_at,
            )

        db.add(app)

        return ApplicationRepository._commit_and_refresh(
            db,
            app,
        )

    @staticmethod
    def _commit_and_refresh(
        db: Session,
        app: Application,
    ) -> Application:

        try:
            db.commit()
            db.refresh(app)

        except SQLAlchemyError:
            db.rollback()
            raise

        return app

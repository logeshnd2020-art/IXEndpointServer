from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.installed_application import InstalledApplication


class InstalledApplicationRepository:

    @staticmethod
    def get_all_by_device(
        db: Session,
        device_id: int,
    ) -> List[InstalledApplication]:
        return (
            db.query(InstalledApplication)
            .filter(InstalledApplication.device_id == device_id)
            .all()
        )

    @staticmethod
    def get_by_identity(
        db: Session,
        device_id: int,
        name: str,
        install_path: Optional[str],
    ) -> Optional[InstalledApplication]:

        query = db.query(InstalledApplication).filter(
            InstalledApplication.device_id == device_id,
            InstalledApplication.name == name,
        )

        if install_path is None:
            query = query.filter(
                InstalledApplication.install_path.is_(None)
            )
        else:
            query = query.filter(
                InstalledApplication.install_path == install_path
            )

        return query.first()

    @staticmethod
    def add(
        db: Session,
        application: InstalledApplication,
    ) -> None:
        db.add(application)

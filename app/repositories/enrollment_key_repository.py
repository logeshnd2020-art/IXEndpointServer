from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import verify_value
from app.models.enrollment_key import EnrollmentKey


class EnrollmentKeyRepository:

    @staticmethod
    def create_enrollment_key(
        db: Session,
        name: str,
        enrollment_key_hash: str,
        expires_at: datetime,
        max_devices: int,
        created_by: str,
    ) -> EnrollmentKey:
        key = EnrollmentKey(
            name=name,
            enrollment_key_hash=enrollment_key_hash,
            expires_at=expires_at,
            max_devices=max_devices,
            devices_registered=0,
            is_active=True,
            created_by=created_by,
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        return key

    @staticmethod
    def get_active_key(db: Session, name: str) -> Optional[EnrollmentKey]:
        now = datetime.now(timezone.utc)
        return (
            db.query(EnrollmentKey)
            .filter(
                EnrollmentKey.name == name,
                EnrollmentKey.is_active.is_(True),
                EnrollmentKey.expires_at > now,
                EnrollmentKey.devices_registered < EnrollmentKey.max_devices,
            )
            .first()
        )

    @staticmethod
    def validate_key(db: Session, enrollment_key: str) -> Optional[EnrollmentKey]:
        now = datetime.now(timezone.utc)
        candidates = (
            db.query(EnrollmentKey)
            .filter(
                EnrollmentKey.is_active.is_(True),
                EnrollmentKey.expires_at > now,
                EnrollmentKey.devices_registered < EnrollmentKey.max_devices,
            )
            .all()
        )

        for key in candidates:
            if verify_value(enrollment_key, key.enrollment_key_hash):
                return key

        return None

    @staticmethod
    def increment_registered_count(db: Session, key: EnrollmentKey) -> EnrollmentKey:
        key.devices_registered += 1
        db.commit()
        db.refresh(key)
        return key

    @staticmethod
    def get_all_enrollment_keys(db: Session):
        return db.query(EnrollmentKey).order_by(EnrollmentKey.id).all()

    @staticmethod
    def get_enrollment_key_by_id(db: Session, key_id: int) -> Optional[EnrollmentKey]:
        return db.query(EnrollmentKey).filter(EnrollmentKey.id == key_id).first()

    @staticmethod
    def delete_enrollment_key(db: Session, key: EnrollmentKey):
        db.delete(key)
        db.commit()
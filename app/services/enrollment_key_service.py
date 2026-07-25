import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.core.security import hash_value
from app.repositories.enrollment_key_repository import EnrollmentKeyRepository
from app.models.enrollment_key import EnrollmentKey


class EnrollmentKeyService:

    @staticmethod
    def generate_enrollment_key(
        db: Session,
        name: str,
        expires_in_hours: int,
        max_devices: int,
        created_by: str,
    ) -> tuple[str, EnrollmentKey]:
        enrollment_key = secrets.token_urlsafe(32)
        enrollment_key_hash = hash_value(enrollment_key)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        key = EnrollmentKeyRepository.create_enrollment_key(
            db=db,
            name=name,
            enrollment_key_hash=enrollment_key_hash,
            expires_at=expires_at,
            max_devices=max_devices,
            created_by=created_by,
        )

        return enrollment_key, key

    @staticmethod
    def validate_key(db: Session, enrollment_key: str) -> Optional[EnrollmentKey]:
        return EnrollmentKeyRepository.validate_key(db, enrollment_key)

    @staticmethod
    def increment_registered_count(db: Session, key: EnrollmentKey) -> EnrollmentKey:
        return EnrollmentKeyRepository.increment_registered_count(db, key)

    @staticmethod
    def list_enrollment_keys(db: Session):
        return EnrollmentKeyRepository.get_all_enrollment_keys(db)

    @staticmethod
    def get_enrollment_key(db: Session, key_id: int) -> Optional[EnrollmentKey]:
        return EnrollmentKeyRepository.get_enrollment_key_by_id(db, key_id)

    @staticmethod
    def delete_enrollment_key(db: Session, key_id: int):
        key = EnrollmentKeyRepository.get_enrollment_key_by_id(db, key_id)
        if not key:
            return None
        EnrollmentKeyRepository.delete_enrollment_key(db, key)
        return key

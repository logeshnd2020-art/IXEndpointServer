from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class EnrollmentKey(Base):
    __tablename__ = "enrollment_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)
    enrollment_key_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    max_devices = Column(Integer, nullable=False, default=1)
    devices_registered = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(150), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

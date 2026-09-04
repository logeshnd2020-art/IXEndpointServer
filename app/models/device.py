from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_uuid = Column(String(100), unique=True, nullable=True)

    hostname = Column(String(100), nullable=False)
    serial_number = Column(String(100), unique=True, nullable=False)
    username = Column(String(100), nullable=False)

    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    platform = Column(String(100), nullable=True)
    os_name = Column(String(100), nullable=True)
    os_version = Column(String(100), nullable=True)
    processor = Column(String(100), nullable=True)
    memory_gb = Column(Float, nullable=True)
    storage_gb = Column(Float, nullable=True)
    status = Column(String(50), nullable=True)

    macos_version = Column(String(50))
    device_model = Column(String(100))
    agent_version = Column(String(20))

    ip_address = Column(String(50))

    device_token_hash = Column(String(255), nullable=True)
    token_created_at = Column(DateTime(timezone=True), nullable=True)
    token_last_used = Column(DateTime(timezone=True), nullable=True)

    registration_date = Column(DateTime(timezone=True), nullable=True)
    registered_by = Column(String(100), nullable=True)
    is_registered = Column(Boolean, default=False, nullable=False)

    is_online = Column(Boolean, default=False)

    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

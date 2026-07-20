from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)

    hostname = Column(String(100), nullable=False)
    serial_number = Column(String(100), unique=True, nullable=False)
    username = Column(String(100), nullable=False)

    macos_version = Column(String(50))
    device_model = Column(String(100))
    agent_version = Column(String(20))

    ip_address = Column(String(50))

    is_online = Column(Boolean, default=False)

    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

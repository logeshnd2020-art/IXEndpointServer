from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    battery_level = Column(Integer, nullable=False)
    logged_in_user = Column(String(100), nullable=True)
    hostname = Column(String(100), nullable=False)
    ip_address = Column(String(50), nullable=False)
    network_name = Column(String(100), nullable=True)
    agent_version = Column(String(100), nullable=False)
    uptime_seconds = Column(Integer, nullable=False)

    device = relationship("Device", backref="telemetry")

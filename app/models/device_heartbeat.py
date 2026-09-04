from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DeviceHeartbeat(Base):
    __tablename__ = "device_heartbeats"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    battery_level = Column(Integer, nullable=False)
    logged_in_user = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=False)
    network_name = Column(String(100), nullable=True)
    # Primary physical network interface's hardware MAC address
    # ("XX:XX:XX:XX:XX:XX"), reported by the agent -- never computed or
    # inferred server-side. NULL until the agent reports one.
    mac_address = Column(String(17), nullable=True)
    uptime_seconds = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    device = relationship("Device", backref="heartbeats")

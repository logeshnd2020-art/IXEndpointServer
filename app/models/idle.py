from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class IdleEvent(Base):
    __tablename__ = "idle_events"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(
        Integer,
        ForeignKey("devices.id"),
        nullable=False,
    )

    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False,
    )

    idle_start = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    idle_end = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    idle_seconds = Column(
        Integer,
        nullable=True,
    )

    local_idle_id = Column(
        Integer,
        nullable=True,
    )

    device = relationship("Device")
    session = relationship("Session")

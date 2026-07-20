from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ActivityEvent(Base):
    __tablename__ = "activity_events"

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

    mouse_clicks = Column(
        Integer,
        nullable=False,
        default=0,
    )

    keyboard_hits = Column(
        Integer,
        nullable=False,
        default=0,
    )

    captured_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    device = relationship("Device")
    session = relationship("Session")

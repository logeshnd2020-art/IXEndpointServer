from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

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

    application_name = Column(
        String(255),
        nullable=False,
    )

    window_title = Column(
        String(500),
        nullable=True,
    )

    start_time = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    end_time = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_seconds = Column(
        Integer,
        nullable=True,
    )

    device = relationship("Device")
    session = relationship("Session")

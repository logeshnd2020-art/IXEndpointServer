from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(
        Integer,
        ForeignKey("devices.id"),
        nullable=False,
    )

    username = Column(String(100), nullable=False)

    login_time = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    logout_time = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )

    device = relationship("Device")

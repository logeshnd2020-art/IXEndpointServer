from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class InstalledApplication(Base):
    __tablename__ = "installed_applications"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    device_id = Column(
        Integer,
        ForeignKey("devices.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    version = Column(
        String(100),
        nullable=True,
    )

    bundle_id = Column(
        String(255),
        nullable=True,
    )

    install_path = Column(
        String(500),
        nullable=True,
    )

    first_seen = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    is_installed = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )

    device = relationship("Device")

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "name",
            "install_path",
            name="uq_installed_app_device_name_path",
        ),
    )

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
import app.models  # noqa: F401  (registers all model tables on Base.metadata)
from app.models.device import Device


@pytest.fixture()
def db_session():
    """
    Fresh in-memory SQLite database per test, built directly from the
    current SQLAlchemy models (not via Alembic) so model-level tests stay
    fast and isolated from migration concerns.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def device(db_session):
    device = Device(
        hostname="test-mac",
        serial_number="SERIAL-0001",
        username="jdoe",
        is_registered=True,
    )

    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)

    return device


def utc(*args, **kwargs):
    return datetime(*args, tzinfo=timezone.utc, **kwargs)

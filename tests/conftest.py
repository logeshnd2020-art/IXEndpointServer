import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core import security
import app.models  # noqa: F401  (registers all model tables on Base.metadata)
from app.main import app
from app.models.device import Device
from app.models.role import Role
from app.models.user import User


@pytest.fixture()
def db_session():
    """
    Fresh in-memory SQLite database per test, built directly from the
    current SQLAlchemy models (not via Alembic) so model-level tests stay
    fast and isolated from migration concerns.
    """
    # StaticPool keeps a single underlying connection alive for the whole
    # engine, which matters for the `client` fixture: FastAPI's TestClient
    # runs each request in a separate worker thread, and a plain SQLite
    # ":memory:" database is otherwise per-connection -- without
    # StaticPool, a request on a different thread would silently get a
    # brand new, empty database ("no such table" errors).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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


@pytest.fixture()
def client(db_session):
    """
    A FastAPI TestClient wired to the same in-memory db_session used by
    the rest of the test suite, so a user/role/device created in a test
    via the ORM is immediately visible to real API requests made through
    this client.
    """

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)


def _make_user(db_session, *, username, password, role_name, email=None):
    role = (
        db_session.query(Role)
        .filter(Role.name == role_name)
        .first()
    )

    if role is None:
        role = Role(name=role_name, description=f"{role_name} role")
        db_session.add(role)
        db_session.commit()
        db_session.refresh(role)

    user = User(
        username=username,
        email=email or f"{username}@example.com",
        password_hash=security.get_password_hash(password),
        is_active=True,
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


# Overridable via env for local/CI use, but the fallback is a deliberately
# obvious test-only string -- never the real monitor account's password --
# so it can't be mistaken for or reused as a production credential. Tests
# that log in as "monitor" via auth_headers() should import this constant
# rather than hardcoding a password literal.
TEST_MONITOR_PASSWORD = os.environ.get("TEST_MONITOR_PASSWORD", "test-only-monitor-fixture-password")

# Same rationale as TEST_MONITOR_PASSWORD above: overridable via env, but the
# fallback is a deliberately obvious test-only string so it can't be mistaken
# for or reused as a production credential. Tests that log in as "admin" via
# auth_headers() should import this constant rather than hardcoding a
# password literal.
TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "test-only-admin-fixture-password")


@pytest.fixture()
def monitor_user(db_session):
    return _make_user(
        db_session,
        username="monitor",
        password=TEST_MONITOR_PASSWORD,
        role_name="MONITOR",
    )


@pytest.fixture()
def admin_user(db_session):
    return _make_user(
        db_session,
        username="admin",
        password=TEST_ADMIN_PASSWORD,
        role_name="Admin",
    )


def auth_headers(client, username, password):
    response = client.post(
        "/api/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

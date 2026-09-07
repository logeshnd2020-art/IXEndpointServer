"""
Phase 3, Item 2 -- confirms the app's actual ASGI lifespan (wired in
app/main.py) records startup/shutdown, AND -- critically for production
safety -- that it does so through the same overridable `get_db`
dependency as every other request, so a test's in-memory database
override is honored here too and the real production database is never
touched by running this test.
"""
from app.models.server_lifecycle_event import ServerLifecycleEvent


def test_client_context_manager_records_startup_and_shutdown(client, db_session):
    # `client` (tests/conftest.py) already entered/exited a
    # `with TestClient(app) as test_client:` block by the time this
    # fixture is handed to the test, which means ASGI startup has
    # already fired. Assert the startup row landed in THIS test's
    # in-memory db_session -- proving lifespan resolved through the
    # dependency override rather than the real SessionLocal/production
    # database.
    startup_rows = (
        db_session.query(ServerLifecycleEvent)
        .filter(ServerLifecycleEvent.event_type == "startup")
        .all()
    )
    assert len(startup_rows) == 1
    assert startup_rows[0].occurred_at is not None


def test_lifespan_shutdown_uses_the_overridden_db_too():
    # Exercise a fresh TestClient enter/exit cycle end-to-end, on an
    # independent in-memory database, and confirm both a startup AND a
    # shutdown row land in it -- never in the real production database.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from fastapi.testclient import TestClient

    from app.core.database import Base, get_db
    import app.models  # noqa: F401
    from app.main import app

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    isolated_session = TestingSessionLocal()

    def override_get_db():
        yield isolated_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app):
            pass  # startup fires on entry, shutdown fires on exit
    finally:
        app.dependency_overrides.pop(get_db, None)

    rows = isolated_session.query(ServerLifecycleEvent).order_by(
        ServerLifecycleEvent.id.asc()
    ).all()
    isolated_session.close()
    engine.dispose()

    assert [r.event_type for r in rows] == ["startup", "shutdown"]

from datetime import datetime, timedelta, timezone

from app.models.session import Session
from app.models.idle import IdleEvent
from app.models.application import Application
from app.services.productivity_service import ProductivityService

from tests.conftest import utc


def _make_session(db_session, device, **overrides):
    defaults = dict(
        device_id=device.id,
        local_session_id=1,
        username="jdoe",
        login_time=utc(2026, 9, 1, 9, 0, 0),
        logout_time=utc(2026, 9, 1, 17, 0, 0),  # 8h = 28800s wall clock
        status="ACTIVE",
        duration_seconds=None,
    )
    defaults.update(overrides)

    session = Session(**defaults)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return session


def test_no_duration_falls_back_to_wall_clock(db_session, device):
    _make_session(db_session, device, duration_seconds=None)

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 28800


def test_working_seconds_uses_stored_sleep_excluded_duration(db_session, device):
    # Wall clock is 8h (28800s), but the agent reports only 5h (18000s) of
    # monitored-awake time -- the rest was macOS sleep.
    _make_session(db_session, device, duration_seconds=18000)

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 18000


def test_duration_greater_than_wall_clock_is_clamped(db_session, device):
    # A bad/corrupt duration value must never inflate working time beyond
    # what the session's own login/logout timestamps allow.
    _make_session(db_session, device, duration_seconds=999_999)

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 28800


def test_open_session_uses_duration_clamped_to_elapsed_wall_clock(db_session, device):
    now = datetime.now(timezone.utc)

    _make_session(
        db_session,
        device,
        login_time=now - timedelta(hours=2),
        logout_time=None,
        duration_seconds=3000,
    )

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 3000


def test_idle_seconds_cannot_exceed_monitored_awake_seconds(db_session, device):
    session = _make_session(db_session, device, duration_seconds=3600)

    # Idle overlap of 20000s comfortably fits inside the 28800s wall clock,
    # but must be clamped to the 3600s monitored-awake duration.
    idle = IdleEvent(
        device_id=device.id,
        session_id=session.id,
        idle_start=utc(2026, 9, 1, 9, 0, 0),
        idle_end=utc(2026, 9, 1, 14, 33, 20),
    )
    db_session.add(idle)
    db_session.commit()

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 3600
    assert result["idle_seconds"] == 3600
    assert result["active_seconds"] == 0


def test_application_elapsed_clamped_to_monitored_working_duration(db_session, device):
    session = _make_session(db_session, device, duration_seconds=600)

    # The application's own start/end span the full 8h wall-clock session,
    # but elapsed time must be clamped to the 600s monitored duration.
    app = Application(
        device_id=device.id,
        session_id=session.id,
        application_name="Xcode",
        start_time=utc(2026, 9, 1, 9, 0, 0),
        end_time=utc(2026, 9, 1, 17, 0, 0),
    )
    db_session.add(app)
    db_session.commit()

    [result] = ProductivityService.get_productivity(db_session)

    [app_usage] = result["applications"]
    assert app_usage["elapsed_seconds"] == 600
    assert app_usage["active_seconds"] == 600

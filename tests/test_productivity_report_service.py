from datetime import date, datetime

from app.models.session import Session
from app.models.idle import IdleEvent
from app.models.application import Application
from app.services.productivity_report_service import ProductivityReportService


def _make_cross_day_session(db_session, device, duration_seconds):
    # Naive datetimes are treated as Asia/Kolkata local time by the
    # service, matching how the endpoint-local agent timestamps are
    # stored. 8h wall clock split 4h/4h across the midnight boundary.
    session = Session(
        device_id=device.id,
        local_session_id=1,
        username="jdoe",
        login_time=datetime(2026, 9, 1, 20, 0, 0),
        logout_time=datetime(2026, 9, 2, 4, 0, 0),
        status="LOGOUT",
        duration_seconds=duration_seconds,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _reports_by_day(db_session):
    reports = ProductivityReportService.get_reports(
        db=db_session,
        report_type="daily",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 2),
    )
    return {r["period_start"]: r for r in reports}


def test_cross_day_session_without_duration_uses_raw_wall_clock(db_session, device):
    _make_cross_day_session(db_session, device, duration_seconds=None)

    by_day = _reports_by_day(db_session)

    assert by_day["2026-09-01"]["working_seconds"] == 14400
    assert by_day["2026-09-02"]["working_seconds"] == 14400


def test_cross_day_session_prorates_monitored_duration_across_days(db_session, device):
    # 8h wall clock, but only 4000s of it was monitored-awake time (the
    # rest was macOS sleep overnight). Each day touched by the session
    # gets an equal share since the session splits it exactly 50/50.
    _make_cross_day_session(db_session, device, duration_seconds=4000)

    by_day = _reports_by_day(db_session)

    assert by_day["2026-09-01"]["working_seconds"] == 2000
    assert by_day["2026-09-02"]["working_seconds"] == 2000

    # The proportional split must reconstruct the reported total.
    total = (
        by_day["2026-09-01"]["working_seconds"]
        + by_day["2026-09-02"]["working_seconds"]
    )
    assert total == 4000


def test_cross_day_session_duration_greater_than_wall_clock_is_clamped_per_day(
    db_session, device
):
    _make_cross_day_session(db_session, device, duration_seconds=999_999)

    by_day = _reports_by_day(db_session)

    # A single day can never receive more than its own wall-clock overlap
    # with the session, even if the stored duration is corrupt.
    assert by_day["2026-09-01"]["working_seconds"] == 14400
    assert by_day["2026-09-02"]["working_seconds"] == 14400


def test_report_idle_seconds_cannot_exceed_monitored_duration_for_period(
    db_session, device
):
    session = _make_cross_day_session(db_session, device, duration_seconds=4000)

    # Idle spans the entire first day's overlap window (4h = 14400s),
    # which is far more than that day's 2000s monitored-awake share.
    idle = IdleEvent(
        device_id=device.id,
        session_id=session.id,
        idle_start=datetime(2026, 9, 1, 20, 0, 0),
        idle_end=datetime(2026, 9, 1, 23, 59, 59),
    )
    db_session.add(idle)
    db_session.commit()

    by_day = _reports_by_day(db_session)

    assert by_day["2026-09-01"]["idle_seconds"] == 2000
    assert by_day["2026-09-01"]["active_seconds"] == 0


def test_report_application_elapsed_clamped_to_monitored_duration_for_period(
    db_session, device
):
    session = _make_cross_day_session(db_session, device, duration_seconds=4000)

    # Application runs the entire first-day overlap (14400s), well beyond
    # that day's 2000s monitored-awake share.
    app = Application(
        device_id=device.id,
        session_id=session.id,
        application_name="Terminal",
        start_time=datetime(2026, 9, 1, 20, 0, 0),
        end_time=datetime(2026, 9, 1, 23, 59, 59),
    )
    db_session.add(app)
    db_session.commit()

    by_day = _reports_by_day(db_session)

    [app_usage] = by_day["2026-09-01"]["applications"]
    assert app_usage["elapsed_seconds"] == 2000

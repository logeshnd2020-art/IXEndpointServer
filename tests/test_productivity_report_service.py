from datetime import date, datetime

from app.models.session import Session
from app.models.idle import IdleEvent
from app.models.application import Application
from app.models.device_heartbeat import DeviceHeartbeat
from app.services.productivity_report_service import ProductivityReportService


def _make_cross_day_session(db_session, device, duration_seconds=None):
    # Naive datetimes are treated as Asia/Kolkata local time by the
    # service, matching how the endpoint-local agent timestamps are
    # stored (session/idle timestamps, and -- since the heartbeat
    # timezone-interpretation fix -- device_heartbeats.timestamp too;
    # see MonitoringWindowService.CLIENT_LOCAL_TZ). 8h wall clock split
    # 4h/4h across the midnight boundary. Day 1's UTC overlap window
    # works out to 14:30-18:30 UTC.
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


def _heartbeat(device, ts, uptime=1000):
    return DeviceHeartbeat(
        device_id=device.id,
        cpu_usage=10.0,
        memory_usage=20.0,
        disk_usage=30.0,
        battery_level=100,
        ip_address="10.0.0.1",
        uptime_seconds=uptime,
        timestamp=ts,
    )


def _reports_by_day(db_session):
    reports = ProductivityReportService.get_reports(
        db=db_session,
        report_type="daily",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 2),
    )
    return {r["period_start"]: r for r in reports}


def test_cross_day_session_without_duration_uses_raw_wall_clock(db_session, device):
    # No heartbeat evidence of a gap -> each day's full wall-clock share
    # of the session counts as monitored (MonitoringWindowService's
    # documented default).
    _make_cross_day_session(db_session, device, duration_seconds=None)

    by_day = _reports_by_day(db_session)

    assert by_day["2026-09-01"]["working_seconds"] == 14400
    assert by_day["2026-09-02"]["working_seconds"] == 14400


def test_duration_seconds_is_ignored_for_report_even_when_present(db_session, device):
    # Canonical accounting design decision: session.duration_seconds is
    # never used, even when present -- confirmed empirically to disagree
    # with real heartbeat evidence by a wide margin. Heartbeats show only
    # the first hour of day 1's 4h (14400s) overlap as monitored; a
    # duration_seconds claiming otherwise must have zero effect.
    # 20:00/21:00 IST == 14:30/15:30 UTC -- the first hour of day 1's
    # 14:30-18:30 UTC overlap window.
    session = _make_cross_day_session(db_session, device, duration_seconds=4000)

    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 20, 0, 0)))
    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 21, 0, 0)))
    db_session.commit()

    by_day = _reports_by_day(db_session)

    # Heartbeat-derived monitored time for day 1 (~1h), not the claimed
    # duration_seconds share (2000s) and not the full 14400s wall clock.
    day1 = by_day["2026-09-01"]
    assert day1["working_seconds"] not in (4000, 2000)
    assert day1["working_seconds"] < 14400


def test_report_idle_seconds_cannot_exceed_monitored_time_for_period(
    db_session, device
):
    # Heartbeats only cover the first hour of day 1's 4h overlap window
    # -- the rest is an unmonitored gap. 20:00/21:00 IST == 14:30/15:30 UTC.
    session = _make_cross_day_session(db_session, device, duration_seconds=None)

    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 20, 0, 0)))
    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 21, 0, 0)))
    db_session.commit()

    # Idle spans the entire first day's overlap window, well beyond the
    # ~1h that was actually monitored.
    idle = IdleEvent(
        device_id=device.id,
        session_id=session.id,
        idle_start=datetime(2026, 9, 1, 20, 0, 0),
        idle_end=datetime(2026, 9, 1, 23, 59, 59),
    )
    db_session.add(idle)
    db_session.commit()

    by_day = _reports_by_day(db_session)

    day1 = by_day["2026-09-01"]
    assert day1["idle_seconds"] == day1["working_seconds"]
    assert day1["active_seconds"] == 0
    assert day1["idle_seconds"] < 14400


def test_off_session_seconds_is_wall_clock_minus_working_when_gap_detected(db_session, device):
    # 4h (14400s) day-1 overlap window, but heartbeats only cover the
    # first hour -- the rest must show up as off_session (no confirmed
    # evidence exists to distinguish it from a session boundary), not
    # silently as 0, and NOT as sleep_seconds (no sleep-evidence signal
    # exists -- see WorkSessionClassifier). 20:00/21:00 IST == 14:30/15:30
    # UTC.
    _make_cross_day_session(db_session, device, duration_seconds=None)

    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 20, 0, 0)))
    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 21, 0, 0)))
    db_session.commit()

    by_day = _reports_by_day(db_session)

    day1 = by_day["2026-09-01"]
    assert day1["sleep_seconds"] == 0
    assert day1["off_session_seconds"] > 0
    assert day1["working_seconds"] + day1["off_session_seconds"] == 14400


def test_off_session_seconds_from_heartbeat_gap_when_duration_unknown(db_session, device):
    # No agent-reported duration_seconds -- the unmonitored remainder must
    # still be derivable from the device's own heartbeat gaps, not
    # silently read as 0. Reported as off_session_seconds, not
    # sleep_seconds -- no sleep-evidence signal exists (WorkSessionClassifier).
    #
    # Session login/logout AND device_heartbeat timestamps are both naive
    # datetimes treated as IST local time (matching the agent's
    # session-sync and heartbeat-write conventions respectively -- see
    # MonitoringWindowService.CLIENT_LOCAL_TZ). login_time 2026-09-01
    # 20:00 IST == 2026-09-01 14:30 UTC, so day 1's overlap window in UTC
    # is 14:30-18:30, and a heartbeat at 2026-09-01 20:00 IST lands at
    # that same 14:30 UTC instant.
    session = _make_cross_day_session(db_session, device, duration_seconds=None)

    # Heartbeats only during the first hour of day 1's 4h UTC overlap
    # (14:30-15:30 UTC == 20:00-21:00 IST), then nothing for the rest of
    # that window -- a large gap inside day 1's window.
    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 20, 0, 0)))
    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 21, 0, 0)))
    db_session.commit()

    by_day = _reports_by_day(db_session)

    day1 = by_day["2026-09-01"]
    # Day 1's 4h (14400s) overlap had heartbeat coverage for only the
    # first hour -- the remaining ~3h must show up as off_session, not as
    # working/idle time, and not as sleep_seconds (no sleep evidence).
    assert day1["sleep_seconds"] == 0
    assert day1["off_session_seconds"] > 0
    assert day1["working_seconds"] + day1["off_session_seconds"] == 14400
    assert day1["working_seconds"] < 14400


def test_report_application_elapsed_excludes_unmonitored_gap_time(
    db_session, device
):
    session = _make_cross_day_session(db_session, device, duration_seconds=None)

    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 20, 0, 0)))
    db_session.add(_heartbeat(device, datetime(2026, 9, 1, 21, 0, 0)))
    db_session.commit()

    # Application runs the entire first-day overlap, well beyond the ~1h
    # that was actually monitored.
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

    day1 = by_day["2026-09-01"]
    [app_usage] = day1["applications"]
    assert app_usage["elapsed_seconds"] == day1["working_seconds"]
    assert app_usage["elapsed_seconds"] < 14400

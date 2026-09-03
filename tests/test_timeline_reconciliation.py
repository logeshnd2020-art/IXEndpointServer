from datetime import date, datetime, timedelta

from app.models.session import Session
from app.models.idle import IdleEvent
from app.models.device_heartbeat import DeviceHeartbeat
from app.services.timeline_service import TimelineService
from app.services.productivity_report_service import ProductivityReportService

from tests.conftest import utc


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


def _segment_totals(segments):
    totals = {}
    for seg in segments:
        totals[seg["type"]] = totals.get(seg["type"], 0) + seg["duration_seconds"]
    return totals


def test_timeline_segment_totals_reconcile_with_report_totals(db_session, device):
    # A single-day session (9:00-17:00, all UTC-aware so both services'
    # naive-datetime timezone conventions are bypassed identically),
    # with one idle stretch and one heartbeat gap (simulated sleep) --
    # exercising ACTIVE, IDLE and SLEEP_GAP all in one session.
    login_time = utc(2026, 9, 1, 9, 0, 0)
    logout_time = utc(2026, 9, 1, 17, 0, 0)

    session = Session(
        device_id=device.id,
        local_session_id=1,
        username="jdoe",
        login_time=login_time,
        logout_time=logout_time,
        status="LOGOUT",
        duration_seconds=None,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # 30 min idle stretch.
    db_session.add(
        IdleEvent(
            device_id=device.id,
            session_id=session.id,
            idle_start=utc(2026, 9, 1, 12, 0, 0),
            idle_end=utc(2026, 9, 1, 12, 30, 0),
        )
    )

    # Heartbeats covering most of the day, with a 2-hour gap (13:00-15:00)
    # standing in for an unmonitored/sleep interval.
    for hour in (9, 10, 11, 12, 13):
        db_session.add(_heartbeat(device, utc(2026, 9, 1, hour, 0, 0)))
    for hour in (15, 16, 17):
        db_session.add(_heartbeat(device, utc(2026, 9, 1, hour, 0, 0)))
    db_session.commit()

    # Path 1: TimelineService (drives the Activity Timeline / Activity
    # Details UI directly).
    segments = TimelineService.build(db_session, session)
    timeline_totals = _segment_totals(segments)

    # Path 2: ProductivityReportService (drives the KPI cards / Period
    # Summary table) -- an entirely independent computation.
    reports = ProductivityReportService.get_reports(
        db=db_session,
        report_type="daily",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 1),
    )
    [report] = reports

    assert timeline_totals.get("ACTIVE", 0) == report["active_seconds"]
    assert timeline_totals.get("IDLE", 0) == report["idle_seconds"]
    assert timeline_totals.get("SLEEP_GAP", 0) == report["sleep_seconds"]

    # And the segments themselves must be gapless/contiguous across the
    # whole session window, with no double-counted or missing time.
    total_seconds = sum(s["duration_seconds"] for s in segments)
    assert total_seconds == int((logout_time - login_time).total_seconds())
    for prev, nxt in zip(segments, segments[1:]):
        assert prev["end"] == nxt["start"]


def test_reconciliation_matches_with_naive_ist_heartbeats(db_session, device):
    """
    Regression test for the heartbeat-timezone-interpretation fix: same
    shape as test_timeline_segment_totals_reconcile_with_report_totals
    (ACTIVE + IDLE + SLEEP_GAP all present in one session), but expressed
    the way real production data actually looks -- session/idle
    timestamps AND device_heartbeats.timestamp all supplied as naive
    local-time (Asia/Kolkata) datetimes (the on-the-wire convention
    written by the agent/DeviceHeartbeatRepository respectively; see
    TimelineService.CLIENT_LOCAL_TZ and MonitoringWindowService's own
    CLIENT_LOCAL_TZ). Every naive value below is the direct IST wall-clock
    equivalent of a specific UTC instant, noted per line. Two short
    "monitored" islands (heartbeats 60s apart, well under the 180s gap
    threshold) bookend one long unmonitored stretch, with an idle event
    inside the first island -- giving deterministic ACTIVE/IDLE/SLEEP_GAP
    totals to check both the reconciliation and their exact values.
    """
    # 14:30/22:30 IST == 09:00/17:00 UTC -- 8h (28800s) session.
    login_time = datetime(2026, 9, 1, 14, 30, 0)
    logout_time = datetime(2026, 9, 1, 22, 30, 0)

    session = Session(
        device_id=device.id,
        local_session_id=1,
        username="jdoe",
        login_time=login_time,
        logout_time=logout_time,
        status="LOGOUT",
        duration_seconds=None,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # 14:32-14:37 IST == 09:02-09:07 UTC -- 5min (300s) idle, inside island A.
    db_session.add(
        IdleEvent(
            device_id=device.id,
            session_id=session.id,
            idle_start=datetime(2026, 9, 1, 14, 32, 0),
            idle_end=datetime(2026, 9, 1, 14, 37, 0),
        )
    )

    # Monitored island A: 14:30-14:40 IST == 09:00-09:10 UTC (10min, 11
    # heartbeats 60s apart -- the session's own start).
    island_a_start = datetime(2026, 9, 1, 14, 30, 0)
    for i in range(11):
        db_session.add(_heartbeat(device, island_a_start + timedelta(minutes=i)))

    # Monitored island B: 22:20-22:30 IST == 16:50-17:00 UTC (10min, 11
    # heartbeats 60s apart -- the session's own end).
    island_b_start = datetime(2026, 9, 1, 22, 20, 0)
    for i in range(11):
        db_session.add(_heartbeat(device, island_b_start + timedelta(minutes=i)))

    db_session.commit()

    segments = TimelineService.build(db_session, session)
    timeline_totals = _segment_totals(segments)

    reports = ProductivityReportService.get_reports(
        db=db_session,
        report_type="daily",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 1),
    )
    [report] = reports

    assert timeline_totals.get("ACTIVE", 0) == report["active_seconds"]
    assert timeline_totals.get("IDLE", 0) == report["idle_seconds"]
    assert timeline_totals.get("SLEEP_GAP", 0) == report["sleep_seconds"]

    # Deterministic totals: 20min (1200s) monitored across both islands,
    # 300s of which is idle -> 900s active; everything else (27600s) is
    # the unmonitored stretch between the islands.
    assert timeline_totals.get("SLEEP_GAP", 0) == 27600
    assert timeline_totals.get("IDLE", 0) == 300
    assert timeline_totals.get("ACTIVE", 0) == 900
    assert (
        timeline_totals.get("ACTIVE", 0)
        + timeline_totals.get("IDLE", 0)
        + timeline_totals.get("SLEEP_GAP", 0)
        == 28800
    )

    total_seconds = sum(s["duration_seconds"] for s in segments)
    assert total_seconds == int((logout_time - login_time).total_seconds())
    for prev, nxt in zip(segments, segments[1:]):
        assert prev["end"] == nxt["start"]


def test_idle_event_spanning_a_heartbeat_gap_is_not_double_counted(db_session, device):
    """
    Reproduces the real production pattern found on 2026-08-27: an idle
    event whose reported span crosses a heartbeat gap boundary. Before
    the canonical-interval fix, ProductivityReportService summed the
    idle event's overlap against the whole session window (including the
    portion that coincided with a heartbeat gap), inflating Idle and
    silently zeroing out Active via the min(idle, working) clamp. The
    fix: idle time is only ever counted within already-monitored
    sub-intervals.
    """
    login_time = utc(2026, 9, 1, 9, 0, 0)
    logout_time = utc(2026, 9, 1, 17, 0, 0)  # 8h = 28800s wall clock

    session = Session(
        device_id=device.id,
        local_session_id=1,
        username="jdoe",
        login_time=login_time,
        logout_time=logout_time,
        status="LOGOUT",
        duration_seconds=None,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # Heartbeats only in a ~60s window near the start and a ~60s window
    # near the end -- almost the entire 8h day is an unmonitored gap.
    db_session.add(_heartbeat(device, login_time))
    db_session.add(_heartbeat(device, login_time.replace(minute=1)))
    db_session.add(_heartbeat(device, logout_time.replace(minute=59, hour=16)))
    db_session.add(_heartbeat(device, logout_time))

    # Idle event spans the ENTIRE session -- exactly the shape that
    # caused the real-world bug (idle 480/569 on 2026-08-27, each
    # spanning far beyond any actually-monitored stretch).
    db_session.add(
        IdleEvent(
            device_id=device.id,
            session_id=session.id,
            idle_start=login_time,
            idle_end=logout_time,
        )
    )
    db_session.commit()

    segments = TimelineService.build(db_session, session)
    timeline_totals = _segment_totals(segments)

    reports = ProductivityReportService.get_reports(
        db=db_session,
        report_type="daily",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 1),
    )
    [report] = reports

    # The idle event's overlap with the heartbeat gap (the vast majority
    # of the 8h span) must be excluded entirely -- not counted as Idle,
    # not counted as Active, not lost, not double-counted. What remains
    # monitored (~120s total) is fully idle, and nothing is Active.
    assert timeline_totals.get("IDLE", 0) < 28800
    assert timeline_totals.get("IDLE", 0) == report["idle_seconds"]
    assert timeline_totals.get("ACTIVE", 0) == report["active_seconds"] == 0
    assert timeline_totals.get("SLEEP_GAP", 0) == report["sleep_seconds"]

    # Full reconciliation: nothing falls through the cracks.
    assert (
        timeline_totals.get("ACTIVE", 0)
        + timeline_totals.get("IDLE", 0)
        + timeline_totals.get("SLEEP_GAP", 0)
        == 28800
    )

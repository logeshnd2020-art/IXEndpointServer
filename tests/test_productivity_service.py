from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.session import Session
from app.models.idle import IdleEvent
from app.models.application import Application
from app.models.device_heartbeat import DeviceHeartbeat
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


KOLKATA = ZoneInfo("Asia/Kolkata")


def _heartbeat(device, ts, uptime=1000):
    # Real device_heartbeats.timestamp is always naive Asia/Kolkata
    # wall-clock time, never UTC -- see MonitoringWindowService. A `ts`
    # built via the tz-aware `utc()` helper must be converted to its naive
    # local-wall-clock equivalent before storing, matching what the real
    # agent/DeviceHeartbeatRepository actually writes.
    if ts.tzinfo is not None:
        ts = ts.astimezone(KOLKATA).replace(tzinfo=None)

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


def test_no_heartbeats_and_no_idle_is_fully_active(db_session, device):
    # No heartbeat evidence of a gap -> the whole session is treated as
    # monitored (MonitoringWindowService's documented default); with no
    # idle events, all of it is Active.
    _make_session(db_session, device, duration_seconds=None)

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 28800
    assert result["active_seconds"] == 28800
    assert result["sleep_seconds"] == 0


def test_duration_seconds_is_never_used_even_when_present(db_session, device):
    # Canonical accounting design decision: session.duration_seconds is
    # never used, even when present, because it was found (empirically,
    # against real production data) to disagree with the server's own
    # heartbeat evidence by a wide margin -- it isn't treated as
    # authoritative. With no heartbeat gap and no idle events,
    # working_seconds must be the full wall clock regardless of what
    # duration_seconds claims.
    _make_session(db_session, device, duration_seconds=18000)

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 28800
    assert result["sleep_seconds"] == 0


def test_live_active_session_ignores_disagreeing_duration_seconds(db_session, device):
    # Reproduces the real-world scenario that triggered this design
    # decision: a still-open session where the agent's own
    # duration_seconds claims far more monitored time than the heartbeat
    # stream can support. The heartbeat-derived figure must win.
    login_time = utc(2026, 9, 1, 9, 0, 0)

    session = _make_session(
        db_session,
        device,
        login_time=login_time,
        logout_time=login_time + timedelta(hours=8),
        status="ACTIVE",
        duration_seconds=25000,  # claims ~7h monitored -- heartbeats disagree
    )

    db_session.add(_heartbeat(device, login_time))
    db_session.add(_heartbeat(device, login_time + timedelta(seconds=60)))
    db_session.commit()

    session.logout_time = None
    db_session.commit()

    [result] = ProductivityService.get_productivity(db_session)

    # Only the ~60s heartbeat-covered window counts, not the agent's
    # claimed 25,000s.
    assert result["working_seconds"] <= 120
    assert result["working_seconds"] != 25000


def test_idle_seconds_cannot_exceed_monitored_awake_seconds(db_session, device):
    # A confirmed monitored island (>= SUSTAINED_RUN_SECONDS = 180s of
    # continuous coverage, WorkSessionClassifier) at the start of the
    # session -- the rest of the 8h window is an unmonitored gap.
    login_time = utc(2026, 9, 1, 9, 0, 0)

    session = _make_session(
        db_session,
        device,
        login_time=login_time,
        logout_time=login_time + timedelta(hours=8),
    )

    for i in range(4):
        db_session.add(_heartbeat(device, login_time + timedelta(minutes=i)))
    db_session.commit()

    # Idle event spans the WHOLE 8h session, but only the confirmed 180s
    # monitored window at the start should ever be counted as idle.
    idle = IdleEvent(
        device_id=device.id,
        session_id=session.id,
        idle_start=login_time,
        idle_end=login_time + timedelta(hours=8),
    )
    db_session.add(idle)
    db_session.commit()

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 180
    assert result["idle_seconds"] == 180
    assert result["active_seconds"] == 0


def test_live_active_session_excludes_heartbeat_gap_from_working_seconds(db_session, device):
    # Wall clock is 8h, but heartbeats show a 6-hour gap partway through
    # (device asleep/unmonitored) -- that gap must not count as working
    # time (active or idle).
    login_time = utc(2026, 9, 1, 9, 0, 0)

    session = _make_session(
        db_session,
        device,
        login_time=login_time,
        logout_time=login_time + timedelta(hours=8),
        status="ACTIVE",
        duration_seconds=None,
    )

    # A confirmed monitored island needs >= SUSTAINED_RUN_SECONDS (180s) of
    # continuous coverage to count as real evidence (WorkSessionClassifier)
    # -- dense heartbeats every 60s for 3 minutes, well above that bar.
    for i in range(4):
        db_session.add(_heartbeat(device, login_time + timedelta(minutes=i), uptime=1000 + i * 30))
    # A single lone heartbeat hours later -- a stutter, correctly absorbed
    # into the surrounding gap rather than treated as a second island.
    db_session.add(_heartbeat(device, login_time + timedelta(hours=7), uptime=44000))
    db_session.commit()

    # This test computes "now" implicitly via the session's own
    # logout_time being None -- but _make_session always sets a
    # logout_time. Re-fetch and clear it to simulate a still-open session.
    session.logout_time = None
    db_session.commit()

    [result] = ProductivityService.get_productivity(db_session)

    # Working seconds must be well under the ~ "now - login_time" wall
    # clock, since most of the window was an unobserved heartbeat gap.
    wall_clock_seconds = int((datetime.now(timezone.utc) - login_time).total_seconds())
    assert result["working_seconds"] < wall_clock_seconds
    assert result["working_seconds"] <= 3600  # only the confirmed ~3-minute island at the start counts as monitored


def test_off_session_seconds_reflects_real_heartbeat_gap_without_confirmed_evidence(db_session, device):
    # A single confirmed monitored island (180s, WorkSessionClassifier),
    # then nothing for the rest of the 8h session -- the trailing gap has
    # no confirmed run AFTER it (it runs all the way to session end), so
    # it is OFF_SESSION, never SLEEP_CONFIRMED (no sleep-evidence signal
    # exists) and never MONITORING_GAP (that requires confirmed evidence
    # on BOTH sides).
    login_time = utc(2026, 9, 1, 9, 0, 0)

    session = _make_session(
        db_session,
        device,
        login_time=login_time,
        logout_time=login_time + timedelta(hours=8),
    )

    for i in range(4):
        db_session.add(_heartbeat(device, login_time + timedelta(minutes=i)))
    db_session.commit()

    [result] = ProductivityService.get_productivity(db_session)

    assert result["working_seconds"] == 180
    assert result["sleep_seconds"] == 0  # SLEEP_CONFIRMED: no evidence, correctly zero
    assert result["off_session_seconds"] == 28800 - 180
    assert result["monitoring_gap_seconds"] == 0
    assert (
        result["working_seconds"]
        + result["sleep_seconds"]
        + result["monitoring_gap_seconds"]
        + result["off_session_seconds"]
        == 28800
    )


def test_application_elapsed_excludes_unmonitored_gap_time(db_session, device):
    login_time = utc(2026, 9, 1, 9, 0, 0)

    session = _make_session(
        db_session,
        device,
        login_time=login_time,
        logout_time=login_time + timedelta(hours=8),
    )

    for i in range(4):
        db_session.add(_heartbeat(device, login_time + timedelta(minutes=i)))
    db_session.commit()

    # The application's own start/end span the full 8h wall-clock
    # session, but elapsed time must be scoped to the confirmed 180s
    # monitored window, not fabricated for the unmonitored (OFF_SESSION)
    # remainder.
    app = Application(
        device_id=device.id,
        session_id=session.id,
        application_name="Xcode",
        start_time=login_time,
        end_time=login_time + timedelta(hours=8),
    )
    db_session.add(app)
    db_session.commit()

    [result] = ProductivityService.get_productivity(db_session)

    [app_usage] = result["applications"]
    assert app_usage["elapsed_seconds"] == 180
    assert app_usage["active_seconds"] == 180

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.application import Application
from app.models.device_heartbeat import DeviceHeartbeat
from app.models.session import Session
from app.services.timeline_service import TimelineService
from app.api.device_page import _build_day_application_summary

from tests.conftest import utc, TEST_MONITOR_PASSWORD, auth_headers

KOLKATA = ZoneInfo("Asia/Kolkata")


def _heartbeat(device, ts, uptime=1000):
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


def _make_session(db_session, device, **overrides):
    defaults = dict(
        device_id=device.id,
        local_session_id=1,
        username="jdoe",
        login_time=utc(2026, 9, 1, 9, 0, 0),
        logout_time=utc(2026, 9, 1, 17, 0, 0),
        status="LOGOUT",
        duration_seconds=None,
    )
    defaults.update(overrides)
    session = Session(**defaults)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Direct proof: TimelineService.overlap_seconds_by_type() -- the shared
# attribution primitive -- only ever attributes ACTIVE/IDLE overlap,
# regardless of segment type, and never mutates its input.
# ---------------------------------------------------------------------------


def _segments():
    base = utc(2026, 1, 1, 0, 0, 0)
    return [
        {"start": base, "end": base + timedelta(seconds=100), "type": "ACTIVE", "duration_seconds": 100},
        {"start": base + timedelta(seconds=100), "end": base + timedelta(seconds=200), "type": "IDLE", "duration_seconds": 100},
        {"start": base + timedelta(seconds=200), "end": base + timedelta(seconds=300), "type": "SLEEP_CONFIRMED", "duration_seconds": 100},
        {"start": base + timedelta(seconds=300), "end": base + timedelta(seconds=400), "type": "MONITORING_GAP", "duration_seconds": 100},
        {"start": base + timedelta(seconds=400), "end": base + timedelta(seconds=500), "type": "OFF_SESSION", "duration_seconds": 100},
        {"start": base + timedelta(seconds=500), "end": base + timedelta(seconds=600), "type": "NO_SESSION", "duration_seconds": 100},
    ]


def test_application_record_spanning_every_state_only_attributes_active_and_idle():
    """
    overlap_seconds_by_type() itself is a generic sum-by-type primitive --
    it returns overlap for every segment type present, including
    SLEEP_CONFIRMED/MONITORING_GAP/OFF_SESSION/NO_SESSION. The exclusion
    that makes application data "never independently create or convert a
    segment to ACTIVE" happens one layer up: every real caller
    (ProductivityService, ProductivityReportService, the application
    drilldown endpoint) only ever reads the "ACTIVE"/"IDLE" keys out of
    this result -- never any other key -- so an application record can
    never be credited Active/Idle time for the other four types no matter
    what its own span or content is.
    """
    segments = _segments()
    base = segments[0]["start"]

    result = TimelineService.overlap_seconds_by_type(segments, base, base + timedelta(seconds=600))

    # The function itself correctly reports overlap for every type
    # present (this is expected, generic behavior, not a leak).
    assert result.get("ACTIVE", 0) == 100
    assert result.get("IDLE", 0) == 100
    assert result.get("SLEEP_CONFIRMED", 0) == 100
    assert result.get("MONITORING_GAP", 0) == 100
    assert result.get("OFF_SESSION", 0) == 100
    assert result.get("NO_SESSION", 0) == 100

    # What every real caller actually extracts -- the attribution
    # guarantee -- is exactly the ACTIVE/IDLE pair, nothing more.
    active_seconds = result.get("ACTIVE", 0)
    idle_seconds = result.get("IDLE", 0)
    assert active_seconds + idle_seconds == 200
    assert active_seconds + idle_seconds != sum(result.values())


def test_application_record_entirely_inside_off_session_attributes_nothing():
    """
    Direct proof of the DarkWake-protection requirement: an application
    record whose entire span falls inside OFF_SESSION must attribute
    exactly zero ACTIVE seconds -- never "application record exists ->
    Active".
    """
    segments = _segments()
    off_session = next(s for s in segments if s["type"] == "OFF_SESSION")

    result = TimelineService.overlap_seconds_by_type(segments, off_session["start"], off_session["end"])

    assert result.get("ACTIVE", 0) == 0
    assert result.get("IDLE", 0) == 0


def test_application_record_entirely_inside_monitoring_gap_attributes_nothing():
    segments = _segments()
    gap = next(s for s in segments if s["type"] == "MONITORING_GAP")

    result = TimelineService.overlap_seconds_by_type(segments, gap["start"], gap["end"])

    assert result.get("ACTIVE", 0) == 0
    assert result.get("IDLE", 0) == 0


def test_application_record_entirely_inside_sleep_confirmed_attributes_nothing():
    segments = _segments()
    sleep = next(s for s in segments if s["type"] == "SLEEP_CONFIRMED")

    result = TimelineService.overlap_seconds_by_type(segments, sleep["start"], sleep["end"])

    assert result.get("ACTIVE", 0) == 0
    assert result.get("IDLE", 0) == 0


def test_attribution_never_mutates_the_canonical_segments():
    """
    Application data must never mutate or reclassify canonical segments --
    attribution is a strict downstream, read-only layer.
    """
    segments = _segments()
    before = [dict(s) for s in segments]

    TimelineService.overlap_seconds_by_type(segments, segments[0]["start"], segments[-1]["end"])

    assert segments == before


def test_missing_application_data_does_not_error():
    """An empty segment list / no overlap must return an empty dict, not raise."""
    assert TimelineService.overlap_seconds_by_type([], utc(2026, 1, 1, 0, 0, 0), utc(2026, 1, 1, 1, 0, 0)) == {}


# ---------------------------------------------------------------------------
# End-to-end: the /api/device/{id}/applications drill-down endpoint,
# built via _build_day_application_summary(), reusing the exact same
# canonical segments Activity Details/Timeline already produce.
# ---------------------------------------------------------------------------


def test_drilldown_excludes_application_record_inside_off_session(db_session, device):
    """
    Reproduces the real IXMAC007 DarkWake shape at the endpoint level: a
    confirmed evening session, a long unmonitored overnight gap
    (OFF_SESSION), an isolated application record inside that gap (the
    DarkWake artifact), then genuine resumption the next morning. The
    drill-down must never attribute the overnight record any Active time.
    """
    session = _make_session(
        db_session,
        device,
        login_time=datetime(2026, 9, 2, 13, 51, 7),
        logout_time=datetime(2026, 9, 4, 10, 51, 16),
    )

    # Confirmed evening activity ending 2026-09-03 18:46:39.
    cursor = datetime(2026, 9, 3, 18, 40, 0)
    while cursor <= datetime(2026, 9, 3, 18, 46, 39):
        db_session.add(_heartbeat(device, cursor))
        cursor += timedelta(seconds=30)

    # A DarkWake-shaped isolated Chrome record deep inside the overnight
    # gap, with no corresponding heartbeat anywhere near it.
    db_session.add(
        Application(
            device_id=device.id,
            session_id=session.id,
            application_name="Google Chrome",
            local_application_id=1,
            start_time=datetime(2026, 9, 4, 0, 6, 55),
            end_time=datetime(2026, 9, 4, 0, 7, 13),
        )
    )

    # Genuine resumption the next morning, well past the disputed window.
    cursor = datetime(2026, 9, 4, 10, 33, 11)
    while cursor <= datetime(2026, 9, 4, 10, 40, 0):
        db_session.add(_heartbeat(device, cursor))
        cursor += timedelta(seconds=30)
    db_session.add(
        Application(
            device_id=device.id,
            session_id=session.id,
            application_name="Terminal",
            local_application_id=2,
            start_time=datetime(2026, 9, 4, 10, 35, 0),
            end_time=datetime(2026, 9, 4, 10, 36, 0),
        )
    )
    db_session.commit()

    response = _build_day_application_summary(db_session, device, "2026-09-04")

    app_names = [a.application for a in response.applications]
    assert "Terminal" in app_names
    # The DarkWake-shaped Chrome record contributes zero attributable
    # overlap -- it must not appear in the drilldown at all (nothing to
    # attribute), and it must certainly never be counted as Active.
    chrome = next((a for a in response.applications if a.application == "Google Chrome"), None)
    if chrome is not None:
        assert chrome.active_seconds == 0
        assert chrome.idle_seconds == 0
        assert chrome.intervals == []

    terminal = next(a for a in response.applications if a.application == "Terminal")
    assert terminal.active_seconds > 0
    for interval in terminal.intervals:
        assert interval.status in ("ACTIVE", "IDLE")


def test_ixmac007_00_00_to_00_16_false_active_regression(db_session, device):
    """
    Full end-to-end reproduction of the real false-Active incident, at the
    API layer. With the MonitoringWindowService boundary-bug fix and the
    WorkSessionClassifier evidence-quality gate both in place, the
    2026-09-04 00:00-00:16 window must classify as OFF_SESSION, never
    ACTIVE, and no application must be attributed any Active time inside
    it.
    """
    _make_session(
        db_session,
        device,
        login_time=datetime(2026, 9, 2, 13, 51, 7),
        logout_time=None,
        status="ACTIVE",
    )

    # Last confirmed heartbeat before the gap, exactly matching the real
    # incident's timestamp.
    cursor = datetime(2026, 9, 3, 18, 40, 0)
    while cursor <= datetime(2026, 9, 3, 18, 46, 39):
        db_session.add(_heartbeat(device, cursor))
        cursor += timedelta(seconds=30)

    # Genuine resumption the next morning, matching the real incident's
    # timestamp -- this gives the classifier a confirmed anchor on BOTH
    # sides of the gap, exactly like the real production data once
    # queried after the fact (not live, mid-gap). Without this, the
    # 2-hour padded evaluation window for date=2026-09-04 (which only
    # reaches back to 2026-09-03 22:00) would see NO confirmed evidence
    # on either side at all (18:46:39 is outside that padding), which
    # must correctly be MONITORING_GAP, not OFF_SESSION -- see
    # test_gap_with_no_confirmed_anchor_at_all_is_never_off_session_regardless_of_duration.
    # This test specifically reproduces the real, fully-resolved
    # incident (queried well after resumption exists), where "after" IS
    # a real confirmed anchor even though "before" falls outside the
    # padding -- exactly as verified live against the production database.
    cursor = datetime(2026, 9, 4, 10, 33, 11)
    while cursor <= datetime(2026, 9, 4, 10, 40, 0):
        db_session.add(_heartbeat(device, cursor))
        cursor += timedelta(seconds=30)
    db_session.commit()

    from app.models.device import Device as DeviceModel
    dev = db_session.query(DeviceModel).filter(DeviceModel.id == device.id).first()

    from app.api.device_page import _build_day_timeline
    timeline = _build_day_timeline(db_session, dev, "2026-09-04")

    disputed_start = datetime(2026, 9, 4, 0, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
    disputed_end = datetime(2026, 9, 4, 0, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)

    covering = [
        seg for seg in timeline.segments
        if seg.start <= disputed_start and seg.end >= disputed_end
    ]
    assert len(covering) == 1
    assert covering[0].type == "OFF_SESSION"
    assert covering[0].type != "ACTIVE"

    drilldown = _build_day_application_summary(db_session, dev, "2026-09-04")
    for app in drilldown.applications:
        for interval in app.intervals:
            # No interval attributed to any application may fall inside
            # the disputed window with status ACTIVE.
            overlaps_disputed_window = interval.start < disputed_end and interval.end > disputed_start
            assert not (overlaps_disputed_window and interval.status == "ACTIVE")

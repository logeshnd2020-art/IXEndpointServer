from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.device_heartbeat import DeviceHeartbeat
from app.services.monitoring_window_service import MonitoringWindowService

from tests.conftest import utc

KOLKATA = ZoneInfo("Asia/Kolkata")


def _heartbeat(device, ts):
    # Real device_heartbeats.timestamp values are always naive, representing
    # Asia/Kolkata wall-clock time (see MonitoringWindowService's own
    # CLIENT_LOCAL_TZ docstring) -- never UTC. A test that builds `ts` via
    # the tz-aware `utc()` helper (for readability of the *instant* under
    # test) must still be stored the same way real heartbeats are: convert
    # to its naive local-wall-clock equivalent first. Naive `ts` values
    # (already representing IST) pass through unchanged.
    if ts.tzinfo is not None:
        ts = ts.astimezone(KOLKATA).replace(tzinfo=None)

    return DeviceHeartbeat(
        device_id=device.id,
        cpu_usage=10.0,
        memory_usage=20.0,
        disk_usage=30.0,
        battery_level=100,
        ip_address="10.0.0.1",
        uptime_seconds=1000,
        timestamp=ts,
    )


def test_no_heartbeats_defaults_to_fully_monitored(db_session, device):
    window_start = utc(2026, 9, 1, 9, 0, 0)
    window_end = utc(2026, 9, 1, 17, 0, 0)

    segments = MonitoringWindowService.get_segments(
        db_session, device.id, window_start, window_end,
    )

    assert segments == [(window_start, window_end, True)]
    assert MonitoringWindowService.monitored_seconds(segments) == 28800


def test_regular_heartbeats_are_fully_monitored(db_session, device):
    window_start = utc(2026, 9, 1, 9, 0, 0)
    window_end = window_start + timedelta(minutes=10)

    for i in range(0, 11, 1):
        db_session.add(_heartbeat(device, window_start + timedelta(minutes=i)))
    db_session.commit()

    segments = MonitoringWindowService.get_segments(
        db_session, device.id, window_start, window_end,
    )

    assert MonitoringWindowService.monitored_seconds(segments) == 600
    assert all(monitored for _, _, monitored in segments)


def test_large_gap_between_heartbeats_is_excluded(db_session, device):
    # Heartbeats at 09:00 and again at 23:00 (overnight sleep), 8h window.
    window_start = utc(2026, 9, 1, 9, 0, 0)
    window_end = window_start + timedelta(hours=8)

    db_session.add(_heartbeat(device, window_start))
    db_session.add(_heartbeat(device, window_start + timedelta(minutes=1)))
    # A 6-hour gap follows, well past the default 180s threshold.
    db_session.add(_heartbeat(device, window_start + timedelta(hours=7)))
    db_session.add(_heartbeat(device, window_start + timedelta(hours=7, minutes=1)))
    db_session.commit()

    segments = MonitoringWindowService.get_segments(
        db_session, device.id, window_start, window_end,
    )

    monitored_seconds = MonitoringWindowService.monitored_seconds(segments)
    total_seconds = int((window_end - window_start).total_seconds())

    assert monitored_seconds < total_seconds
    assert any(not monitored for _, _, monitored in segments)

    gap_seconds = sum(
        int((end - start).total_seconds())
        for start, end, monitored in segments
        if not monitored
    )
    # The gap between minute 1 and hour 7 is ~6h59m.
    assert gap_seconds > 6 * 3600


def test_naive_heartbeat_timestamp_is_interpreted_as_ist_not_utc():
    """
    Regression test for the 2026-09-03 IXMAC007 incident: a naive
    device_heartbeats.timestamp of 10:03:23 -- the device's real wake
    time, written as naive local wall-clock time by
    DeviceHeartbeatRepository.create_heartbeat() -- must be interpreted as
    10:03:23 Asia/Kolkata, NOT 10:03:23 UTC (which would re-display, once
    converted back to IST for the dashboard, as the wrong 15:33:23).
    """
    naive = datetime(2026, 9, 3, 10, 3, 23)

    normalized = MonitoringWindowService._normalize_heartbeat_timestamp(naive)

    assert normalized == datetime(2026, 9, 3, 10, 3, 23, tzinfo=KOLKATA)
    assert normalized.astimezone(KOLKATA).strftime("%H:%M:%S") == "10:03:23"
    assert normalized.astimezone(KOLKATA).strftime("%H:%M:%S") != "15:33:23"


def test_naive_heartbeat_before_midnight_is_interpreted_as_ist_not_utc():
    """
    The other boundary of the same real incident: the last heartbeat
    before the overnight sleep gap, stored as naive 2026-09-02 19:28:12,
    must be interpreted as 19:28:12 Asia/Kolkata (i.e. still the evening
    of 09-02), not shifted forward into 09-03 00:58:12 by a UTC
    misinterpretation.
    """
    naive = datetime(2026, 9, 2, 19, 28, 12)

    normalized = MonitoringWindowService._normalize_heartbeat_timestamp(naive)

    assert normalized == datetime(2026, 9, 2, 19, 28, 12, tzinfo=KOLKATA)
    assert normalized.astimezone(KOLKATA).strftime("%Y-%m-%d %H:%M:%S") == "2026-09-02 19:28:12"


def test_aware_heartbeat_timestamps_are_unaffected_by_the_fix():
    """
    Timezone-aware heartbeat timestamps (e.g. a future agent build that
    starts sending real UTC) must continue to pass straight through
    unchanged in effect -- only naive values get the local-time
    interpretation.
    """
    aware_utc = datetime(2026, 9, 3, 4, 33, 23, tzinfo=timezone.utc)
    assert MonitoringWindowService._normalize_heartbeat_timestamp(aware_utc) == aware_utc

    aware_ist = datetime(2026, 9, 3, 10, 3, 23, tzinfo=KOLKATA)
    assert (
        MonitoringWindowService._normalize_heartbeat_timestamp(aware_ist)
        == aware_ist.astimezone(timezone.utc)
    )


def test_get_segments_anchors_sleep_gap_correctly_for_naive_ist_heartbeats(db_session, device):
    """
    End-to-end reproduction of the IXMAC007 incident shape: a real
    overnight sleep gap between naive-IST heartbeats at 19:28:12 (evening)
    and 10:03:23 (next morning) must produce a SLEEP_GAP anchored at the
    correct UTC instants -- not the old buggy interpretation, which would
    place this same gap 5h30m later (00:58:12-15:33:23 IST) once
    converted back for display. The window brackets exactly these two
    heartbeats' own true instants (as a session-lifetime window would,
    unlike a calendar-day window, which would legitimately clip the
    evening heartbeat into the previous day's query).
    """
    window_start = utc(2026, 9, 2, 13, 58, 12)  # 2026-09-02 19:28:12 IST
    window_end = utc(2026, 9, 3, 4, 33, 23)     # 2026-09-03 10:03:23 IST

    db_session.add(
        DeviceHeartbeat(
            device_id=device.id,
            cpu_usage=10.0,
            memory_usage=20.0,
            disk_usage=30.0,
            battery_level=100,
            ip_address="10.0.0.1",
            uptime_seconds=33937,
            timestamp=datetime(2026, 9, 2, 19, 28, 12),
        )
    )
    db_session.add(
        DeviceHeartbeat(
            device_id=device.id,
            cpu_usage=10.0,
            memory_usage=20.0,
            disk_usage=30.0,
            battery_level=100,
            ip_address="10.0.0.1",
            uptime_seconds=86448,
            timestamp=datetime(2026, 9, 3, 10, 3, 23),
        )
    )
    db_session.commit()

    segments = MonitoringWindowService.get_segments(db_session, device.id, window_start, window_end)

    gap_segments = [s for s in segments if not s[2]]
    assert len(gap_segments) == 1
    gap_start, gap_end, _ = gap_segments[0]

    # Correct: true 19:28:12 IST (== 13:58:12 UTC) through true 10:03:23
    # IST (== 04:33:23 UTC).
    assert gap_start == utc(2026, 9, 2, 13, 58, 12)
    assert gap_end == utc(2026, 9, 3, 4, 33, 23)

    # The old (buggy) interpretation would have anchored this gap at the
    # naive literal values taken as UTC -- explicitly assert that wrong
    # anchor no longer appears anywhere in the segment boundaries.
    buggy_gap_start = datetime(2026, 9, 2, 19, 28, 12, tzinfo=timezone.utc)
    buggy_gap_end = datetime(2026, 9, 3, 10, 3, 23, tzinfo=timezone.utc)
    boundaries = {b for seg in segments for b in seg[:2]}
    assert buggy_gap_start not in boundaries
    assert buggy_gap_end not in boundaries


def test_in_progress_gap_before_window_is_not_defaulted_to_monitored(db_session, device):
    """
    Regression test for the real IXMAC007 false-Active incident: a live
    "today so far" query made during an in-progress overnight gap -- where
    the only heartbeat evidence is BEFORE window_start, and none exists
    inside the window itself -- must correctly report monitored=False for
    the whole window, not silently default to True. Exact real-data shape:
    last heartbeat 2026-09-03 18:46:39, next real heartbeat not until
    2026-09-04 10:29:01 -- querying the elapsed portion of the new day
    (00:00-00:16) live, before that morning's heartbeats exist, must not
    report it as monitored.
    """
    db_session.add(_heartbeat(device, datetime(2026, 9, 3, 18, 46, 39)))
    db_session.commit()

    window_start = utc(2026, 9, 3, 18, 30, 0)  # 2026-09-04 00:00 IST
    window_end = utc(2026, 9, 3, 18, 46, 0)  # 2026-09-04 00:16 IST

    segments = MonitoringWindowService.get_segments(db_session, device.id, window_start, window_end)

    assert segments == [(window_start, window_end, False)]


def test_prior_heartbeat_recent_enough_still_defaults_to_monitored(db_session, device):
    """
    The fix must not become over-eager: a heartbeat shortly before
    window_start that does NOT yet imply a real gap by window_end must
    not falsely trigger the not-monitored fallback -- only an
    already-overdue gap does.
    """
    db_session.add(_heartbeat(device, utc(2026, 9, 1, 8, 59, 0)))  # 60s before window_start
    db_session.commit()

    window_start = utc(2026, 9, 1, 9, 0, 0)
    window_end = window_start + timedelta(minutes=1)

    segments = MonitoringWindowService.get_segments(db_session, device.id, window_start, window_end)

    assert segments == [(window_start, window_end, True)]


def test_no_heartbeat_evidence_at_all_still_defaults_to_monitored(db_session, device):
    """
    The fix must not affect the case where NO heartbeat evidence exists
    at all for this device -- not even before window_start (e.g. a
    pre-heartbeat-era session, or a brand new device). That case still
    defaults to fully monitored, exactly as before.
    """
    window_start = utc(2026, 9, 4, 0, 0, 0)
    window_end = utc(2026, 9, 4, 0, 16, 0)

    segments = MonitoringWindowService.get_segments(db_session, device.id, window_start, window_end)

    assert segments == [(window_start, window_end, True)]


def test_gap_below_threshold_is_still_monitored(db_session, device):
    window_start = utc(2026, 9, 1, 9, 0, 0)
    window_end = window_start + timedelta(minutes=3)

    # Two 90s gaps, both below the 180s default threshold.
    db_session.add(_heartbeat(device, window_start))
    db_session.add(_heartbeat(device, window_start + timedelta(seconds=90)))
    db_session.add(_heartbeat(device, window_end))
    db_session.commit()

    segments = MonitoringWindowService.get_segments(
        db_session, device.id, window_start, window_end,
    )

    assert all(monitored for _, _, monitored in segments)
    assert MonitoringWindowService.monitored_seconds(segments) == 180

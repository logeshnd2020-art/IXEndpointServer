from datetime import timedelta

from app.models.device_heartbeat import DeviceHeartbeat
from app.services.monitoring_window_service import MonitoringWindowService

from tests.conftest import utc


def _heartbeat(device, ts):
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

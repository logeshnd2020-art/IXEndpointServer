"""
7.8.0 -- end-to-end integration: proves the reason-evidence groundwork is
correctly wired into the real dashboard timeline path (_build_day_timeline)
while leaving TimelineService.build() itself, the accounting invariant,
ACTIVE/IDLE, MONITORING_GAP, NO_SESSION, and productivity/application
attribution completely untouched.

Uses a fixed, safely-past date (2026-09-01) throughout -- matching the
convention already established in tests/test_timeline_reconciliation.py --
so _build_day_timeline's `effective_end = min(day_end_utc, now)` "don't
fabricate data for the future" clamp never clips this test's own synthetic
data relative to whatever the real wall-clock happens to be when the suite
runs.
"""
from datetime import timedelta

from app.models.session import Session
from app.models.device_heartbeat import DeviceHeartbeat
from app.models.agent_lifecycle_event import AgentLifecycleEvent
from app.services.timeline_service import TimelineService
from app.services.productivity_service import ProductivityService
from app.api.device_page import _build_day_timeline

from tests.conftest import utc

DAY = "2026-09-01"


def _heartbeat(device, ts, uptime=1000):
    return DeviceHeartbeat(
        device_id=device.id, cpu_usage=10.0, memory_usage=20.0, disk_usage=30.0,
        battery_level=100, ip_address="10.0.0.1", uptime_seconds=uptime, timestamp=ts,
    )


def _build_session_with_gap(db_session, device):
    login_time = utc(2026, 9, 1, 9, 0, 0)
    logout_time = utc(2026, 9, 1, 17, 0, 0)

    session = Session(
        device_id=device.id, local_session_id=1, username="jdoe",
        login_time=login_time, logout_time=logout_time, status="LOGOUT",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # Dense heartbeats 9:00-13:00 and 13:30-17:00, with a genuine 30-minute
    # gap (13:00-13:30) in between -- well over the classifier's 180s
    # threshold, but well UNDER the 3600s OFF_SESSION_CEILING, so this
    # stays MONITORING_GAP (not OFF_SESSION) as intended by this test.
    cursor = login_time
    while cursor < utc(2026, 9, 1, 13, 0, 0):
        db_session.add(_heartbeat(device, cursor))
        cursor += timedelta(minutes=1)
    cursor = utc(2026, 9, 1, 13, 30, 0)
    while cursor < logout_time:
        db_session.add(_heartbeat(device, cursor))
        cursor += timedelta(minutes=1)
    db_session.commit()

    return session, login_time, logout_time


class TestReasonWiredIntoDashboardTimelineOnly:
    def test_build_day_timeline_attaches_reason_to_the_gap(self, db_session, device):
        _build_session_with_gap(db_session, device)

        # Discover the gap's actual [start, end) as the classifier itself
        # reports it (rather than assuming it matches the UTC literals
        # used to build the heartbeats -- DeviceHeartbeat.timestamp is
        # naive-IST by convention, and SQLite strips tzinfo from the
        # aware values this helper writes directly via the ORM, so the
        # only robust way to align a SLEEP/WAKE event with the resulting
        # gap is to read the gap's own reported boundaries back).
        before = _build_day_timeline(db_session, device, DAY)
        gap_before = [s for s in before.segments if s.type == "MONITORING_GAP"]
        assert len(gap_before) == 1

        db_session.add(
            AgentLifecycleEvent(
                device_id=device.id, event_uid="sleep-1", event_type="SLEEP",
                event_time=gap_before[0].start, collected_at=gap_before[0].start,
            )
        )
        db_session.add(
            AgentLifecycleEvent(
                device_id=device.id, event_uid="wake-1", event_type="WAKE",
                event_time=gap_before[0].end, collected_at=gap_before[0].end,
                wake_reason="UserWake",
            )
        )
        db_session.commit()

        response = _build_day_timeline(db_session, device, DAY)
        gap_segments = [s for s in response.segments if s.type == "MONITORING_GAP"]

        assert len(gap_segments) == 1
        assert gap_segments[0].reason == "SLEEP"
        # type is unchanged -- MONITORING_GAP, never reclassified to
        # SLEEP_CONFIRMED just because a reason exists.
        assert gap_segments[0].type == "MONITORING_GAP"

    def test_gap_with_no_agent_evidence_still_shows_reason_none(self, db_session, device):
        _build_session_with_gap(db_session, device)

        response = _build_day_timeline(db_session, device, DAY)
        gap_segments = [s for s in response.segments if s.type == "MONITORING_GAP"]

        assert len(gap_segments) == 1
        assert gap_segments[0].reason is None  # honest fallback, unchanged

    def test_timeline_service_build_never_produces_a_reason_key_itself(self, db_session, device):
        # TimelineService.build() is the shared canonical service used by
        # ProductivityService/ProductivityReportService/application
        # attribution as well -- it must never itself add `reason`,
        # regardless of what agent_lifecycle_events contains. Only
        # device_page._build_day_timeline calls attach_reason.
        session, login_time, logout_time = _build_session_with_gap(db_session, device)
        db_session.add(
            AgentLifecycleEvent(
                device_id=device.id, event_uid="sleep-1", event_type="SLEEP",
                event_time=utc(2026, 9, 1, 13, 0, 0), collected_at=utc(2026, 9, 1, 13, 0, 0),
            )
        )
        db_session.commit()

        segments = TimelineService.build(db_session, session, login_time, logout_time)
        assert all("reason" not in seg for seg in segments)


class TestAccountingInvariantUnaffected:
    def test_total_duration_unchanged_with_agent_evidence_present(self, db_session, device):
        session, login_time, logout_time = _build_session_with_gap(db_session, device)
        db_session.add(
            AgentLifecycleEvent(
                device_id=device.id, event_uid="sleep-1", event_type="SLEEP",
                event_time=utc(2026, 9, 1, 13, 0, 0), collected_at=utc(2026, 9, 1, 13, 0, 0),
            )
        )
        db_session.commit()

        response = _build_day_timeline(db_session, device, DAY)
        total = sum(s.duration_seconds for s in response.segments if s.type != "NO_SESSION")
        assert total == int((logout_time - login_time).total_seconds())

    def test_productivity_service_totals_identical_with_and_without_agent_evidence(self, db_session, device):
        _build_session_with_gap(db_session, device)
        before = ProductivityService.get_productivity(db_session)

        db_session.add(
            AgentLifecycleEvent(
                device_id=device.id, event_uid="sleep-1", event_type="SLEEP",
                event_time=utc(2026, 9, 1, 13, 0, 0), collected_at=utc(2026, 9, 1, 13, 0, 0),
            )
        )
        db_session.commit()
        after = ProductivityService.get_productivity(db_session)

        # ProductivityService never reads agent_lifecycle_events or
        # `reason` -- its output must be byte-identical either way.
        assert before == after


class TestNoSessionRemainsDistinctFromMonitoringGap:
    def test_no_session_segments_never_receive_a_reason(self, db_session, device):
        # A session that only covers part of the day -- the rest is
        # NO_SESSION, which must never be conflated with MONITORING_GAP
        # or receive agent-lifecycle-derived reason evidence.
        session = Session(
            device_id=device.id, local_session_id=1, username="jdoe",
            login_time=utc(2026, 9, 1, 9, 0, 0), logout_time=utc(2026, 9, 1, 10, 0, 0),
            status="LOGOUT",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        for m in range(60):
            db_session.add(_heartbeat(device, utc(2026, 9, 1, 9, 0, 0) + timedelta(minutes=m)))
        db_session.commit()

        db_session.add(
            AgentLifecycleEvent(
                device_id=device.id, event_uid="sleep-1", event_type="SLEEP",
                event_time=utc(2026, 9, 1, 12, 0, 0), collected_at=utc(2026, 9, 1, 12, 0, 0),
            )
        )
        db_session.commit()

        response = _build_day_timeline(db_session, device, DAY)
        no_session_segments = [s for s in response.segments if s.type == "NO_SESSION"]
        assert no_session_segments  # the rest of the day has no session
        assert all(s.reason is None for s in no_session_segments)
        assert all(s.type != "MONITORING_GAP" for s in no_session_segments)

"""
7.8.0 -- agent_evidence_service: the core evidence-derivation logic.
Covers Sleep/Wake, DarkWake, Restart/Shutdown (planned + unplanned +
pending), Agent lifecycle (started/restarted/stopped/unexpected
recovery), Network vs Server unavailability (including the explicit
ambiguity carve-out), and the server-outage fallback -- exactly the
state/reason decision matrix from the approved specification.
"""
from datetime import datetime, timedelta, timezone

from app.models.agent_lifecycle_event import AgentLifecycleEvent
from app.models.server_lifecycle_event import ServerLifecycleEvent
from app.services.agent_evidence_service import (
    BOOTTIME_TOLERANCE_SECONDS,
    RESTART_VS_SHUTDOWN_GAP_SECONDS,
    attach_reason,
    get_reason_evidence,
)


def utc(*a, **kw):
    return datetime(*a, tzinfo=timezone.utc, **kw)


def _ev(db_session, device, event_type, event_time, **kw):
    ev = AgentLifecycleEvent(
        device_id=device.id,
        event_uid=f"{event_type}-{event_time.isoformat()}-{kw.get('boottime', '')}",
        event_type=event_type,
        event_time=event_time,
        collected_at=event_time,
        **kw,
    )
    db_session.add(ev)
    db_session.commit()
    return ev


WIN_START = utc(2026, 9, 7, 0, 0, 0)
WIN_END = utc(2026, 9, 8, 0, 0, 0)


class TestSleepWake:
    def test_sleep_to_wake_produces_sleep_reason(self, db_session, device):
        _ev(db_session, device, "SLEEP", utc(2026, 9, 7, 22, 0, 0))
        _ev(db_session, device, "WAKE", utc(2026, 9, 8, 6, 0, 0), wake_reason="UserWake")

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        sleep_ev = [e for e in evidence if e.reason == "SLEEP"]
        assert len(sleep_ev) == 1
        assert sleep_ev[0].start == utc(2026, 9, 7, 22, 0, 0)
        assert sleep_ev[0].end == utc(2026, 9, 8, 6, 0, 0)

    def test_sleep_with_no_wake_yet_is_open_ended_not_dropped(self, db_session, device):
        _ev(db_session, device, "SLEEP", utc(2026, 9, 7, 22, 0, 0))

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "SLEEP" for e in evidence)

    def test_monitoring_gap_with_no_sleep_event_is_never_labeled_sleep(self, db_session, device):
        # No SLEEP event at all -- a plain heartbeat-style gap must never
        # be classified as Sleep. This is the direct enforcement of
        # "never classify every monitoring gap as Sleep."
        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert not any(e.reason == "SLEEP" for e in evidence)


class TestDarkWake:
    def test_darkwake_reason_is_recorded_but_never_produces_active(self, db_session, device):
        wake = _ev(db_session, device, "WAKE", utc(2026, 9, 8, 3, 0, 0), wake_reason="DarkWake")
        assert wake.wake_reason == "DarkWake"

        # Structural proof: attach_reason only ever sets `reason` on
        # ACTIVE/IDLE/NO_SESSION-excluded (gap-type) segments -- a
        # DarkWake event can never cause an ACTIVE segment to appear,
        # because attach_reason never touches ACTIVE/IDLE segments at all.
        segments = [
            {"start": utc(2026, 9, 8, 2, 0, 0), "end": utc(2026, 9, 8, 4, 0, 0), "type": "ACTIVE", "duration_seconds": 7200},
        ]
        result = attach_reason(segments, device.id, db_session)
        assert "reason" not in result[0] or result[0].get("reason") is None


class TestRestartShutdown:
    def test_short_gap_with_boottime_change_is_confirmed_restart(self, db_session, device):
        old_boot = utc(2026, 9, 7, 8, 0, 0)
        new_boot = utc(2026, 9, 7, 14, 5, 0)

        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 8, 0, 5), boottime=old_boot)
        _ev(db_session, device, "SHUTDOWN_OR_RESTART_IMMINENT", utc(2026, 9, 7, 14, 0, 0))
        _ev(
            db_session, device, "AGENT_STARTED",
            utc(2026, 9, 7, 14, 0, 0) + timedelta(seconds=RESTART_VS_SHUTDOWN_GAP_SECONDS - 30),
            boottime=new_boot,
        )

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "RESTART" for e in evidence)
        assert not any(e.reason == "SHUTDOWN" for e in evidence)

    def test_long_gap_with_boottime_change_is_confirmed_shutdown(self, db_session, device):
        old_boot = utc(2026, 9, 7, 8, 0, 0)
        new_boot = utc(2026, 9, 7, 20, 0, 0)

        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 8, 0, 5), boottime=old_boot)
        _ev(db_session, device, "SHUTDOWN_OR_RESTART_IMMINENT", utc(2026, 9, 7, 14, 0, 0))
        _ev(
            db_session, device, "AGENT_STARTED",
            utc(2026, 9, 7, 14, 0, 0) + timedelta(seconds=RESTART_VS_SHUTDOWN_GAP_SECONDS + 30),
            boottime=new_boot,
        )

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "SHUTDOWN" for e in evidence)
        assert not any(e.reason == "RESTART" for e in evidence)

    def test_shutdown_imminent_with_no_resumption_yet_is_pending_not_confirmed(self, db_session, device):
        _ev(db_session, device, "SHUTDOWN_OR_RESTART_IMMINENT", utc(2026, 9, 7, 14, 0, 0))

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "SHUTDOWN_OR_RESTART_PENDING" for e in evidence)
        assert not any(e.reason in ("RESTART", "SHUTDOWN") for e in evidence)

    def test_device_disappearing_with_no_shutdown_imminent_event_is_never_shutdown(self, db_session, device):
        # No SHUTDOWN_OR_RESTART_IMMINENT at all -- disappearance alone
        # must never be interpreted as Shutdown.
        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert not any(e.reason in ("SHUTDOWN", "SHUTDOWN_OR_RESTART_PENDING") for e in evidence)

    def test_boottime_jitter_within_tolerance_is_not_a_restart(self, db_session, device):
        boot = utc(2026, 9, 7, 8, 0, 0)
        jittered = boot + timedelta(seconds=BOOTTIME_TOLERANCE_SECONDS - 5)

        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 8, 0, 5), boottime=boot)
        _ev(db_session, device, "SHUTDOWN_OR_RESTART_IMMINENT", utc(2026, 9, 7, 14, 0, 0))
        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 14, 0, 30), boottime=jittered)

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        # Boottime effectively unchanged (within tolerance) despite the
        # shutdown warning -- cannot confirm a reboot actually occurred;
        # must not guess RESTART or SHUTDOWN.
        assert not any(e.reason in ("RESTART", "SHUTDOWN") for e in evidence)

    def test_boottime_change_beyond_tolerance_without_warning_is_unplanned_restart(self, db_session, device):
        old_boot = utc(2026, 9, 7, 8, 0, 0)
        new_boot = utc(2026, 9, 7, 15, 0, 0)

        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 8, 0, 5), boottime=old_boot)
        # No SHUTDOWN_OR_RESTART_IMMINENT -- power loss / panic / forced reset.
        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 15, 0, 5), boottime=new_boot)

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "RESTART_UNPLANNED" for e in evidence)
        assert not any(e.reason == "RESTART" for e in evidence)


class TestAgentLifecycle:
    def test_agent_started_with_same_boottime_and_graceful_stop_is_agent_restart(self, db_session, device):
        boot = utc(2026, 9, 7, 8, 0, 0)
        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 8, 0, 5), boottime=boot)
        _ev(db_session, device, "AGENT_STOPPED", utc(2026, 9, 7, 10, 0, 0))
        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 10, 0, 10), boottime=boot)

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "AGENT_RESTART" for e in evidence)
        assert not any(e.reason == "UNEXPECTED_AGENT_RECOVERY" for e in evidence)

    def test_agent_started_with_same_boottime_and_no_graceful_stop_is_unexpected_recovery(self, db_session, device):
        boot = utc(2026, 9, 7, 8, 0, 0)
        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 8, 0, 5), boottime=boot)
        # No AGENT_STOPPED -- crash, kill -9, or forced terminate; cannot
        # tell which.
        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 10, 0, 10), boottime=boot)

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "UNEXPECTED_AGENT_RECOVERY" for e in evidence)
        # Must never be labeled a confirmed crash.
        assert not any("CRASH" in e.reason for e in evidence)

    def test_first_ever_agent_started_produces_no_comparison_evidence(self, db_session, device):
        _ev(db_session, device, "AGENT_STARTED", utc(2026, 9, 7, 8, 0, 5), boottime=utc(2026, 9, 7, 8, 0, 0))

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert not any(e.reason in ("AGENT_RESTART", "UNEXPECTED_AGENT_RECOVERY", "RESTART_UNPLANNED") for e in evidence)

    def test_agent_stopped_produces_agent_stopped_reason(self, db_session, device):
        _ev(db_session, device, "AGENT_STOPPED", utc(2026, 9, 7, 18, 0, 0))
        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "AGENT_STOPPED" for e in evidence)


class TestNetworkVsServerUnavailable:
    def test_network_unavailable_pair_produces_network_reason(self, db_session, device):
        _ev(db_session, device, "NETWORK_UNAVAILABLE", utc(2026, 9, 7, 9, 0, 0), reachability_target="default_route")
        _ev(db_session, device, "NETWORK_RECOVERED", utc(2026, 9, 7, 9, 30, 0))

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "NETWORK_UNAVAILABLE" for e in evidence)

    def test_server_unavailable_pair_produces_server_reason(self, db_session, device):
        _ev(db_session, device, "SERVER_UNAVAILABLE", utc(2026, 9, 7, 9, 0, 0), reachability_target="server_endpoint")
        _ev(db_session, device, "SERVER_RECOVERED", utc(2026, 9, 7, 9, 30, 0))

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert any(e.reason == "SERVER_UNAVAILABLE" for e in evidence)

    def test_no_reachability_event_at_all_leaves_gap_unannotated(self, db_session, device):
        # The explicit ambiguity carve-out: when the client cannot tell
        # Network from Server apart (e.g. an ambiguous timeout), it emits
        # NEITHER event. Proven here at the evidence layer: with no event
        # of either type, neither reason is ever produced.
        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        assert not any(e.reason in ("NETWORK_UNAVAILABLE", "SERVER_UNAVAILABLE") for e in evidence)


class TestServerOutageFallback:
    def test_server_lifecycle_outage_maps_only_to_server_unavailable(self, db_session, device):
        db_session.add(ServerLifecycleEvent(event_type="shutdown", occurred_at=utc(2026, 9, 7, 10, 0, 0)))
        db_session.add(ServerLifecycleEvent(event_type="startup", occurred_at=utc(2026, 9, 7, 10, 25, 0)))
        db_session.commit()

        evidence = get_reason_evidence(db_session, device.id, WIN_START, WIN_END)
        server_outage = [e for e in evidence if e.start == utc(2026, 9, 7, 10, 0, 0)]
        assert len(server_outage) == 1
        assert server_outage[0].reason == "SERVER_UNAVAILABLE"
        # Requirement 8: server outage must never be interpreted as
        # device shutdown/restart/sleep/agent-stopped.
        assert server_outage[0].reason not in ("SHUTDOWN", "RESTART", "SLEEP", "AGENT_STOPPED")


class TestAttachReasonDoesNotTouchTypeOrDuration:
    def test_attach_reason_only_sets_reason_key_never_type_or_duration(self, db_session, device):
        _ev(db_session, device, "SLEEP", utc(2026, 9, 7, 1, 0, 0))
        _ev(db_session, device, "WAKE", utc(2026, 9, 7, 5, 0, 0))

        segments = [
            {"start": utc(2026, 9, 7, 1, 0, 0), "end": utc(2026, 9, 7, 5, 0, 0), "type": "MONITORING_GAP", "duration_seconds": 14400},
        ]
        result = attach_reason(segments, device.id, db_session)

        assert result[0]["type"] == "MONITORING_GAP"  # unchanged
        assert result[0]["duration_seconds"] == 14400  # unchanged
        assert result[0]["reason"] == "SLEEP"  # only new field added

    def test_gap_with_no_evidence_stays_unannotated(self, db_session, device):
        segments = [
            {"start": utc(2026, 9, 7, 1, 0, 0), "end": utc(2026, 9, 7, 5, 0, 0), "type": "MONITORING_GAP", "duration_seconds": 14400},
        ]
        result = attach_reason(segments, device.id, db_session)
        assert result[0].get("reason") is None

    def test_active_and_idle_segments_never_receive_a_reason(self, db_session, device):
        _ev(db_session, device, "SLEEP", utc(2026, 9, 7, 1, 0, 0))
        _ev(db_session, device, "WAKE", utc(2026, 9, 7, 5, 0, 0))

        segments = [
            {"start": utc(2026, 9, 7, 1, 0, 0), "end": utc(2026, 9, 7, 5, 0, 0), "type": "ACTIVE", "duration_seconds": 14400},
            {"start": utc(2026, 9, 7, 1, 0, 0), "end": utc(2026, 9, 7, 5, 0, 0), "type": "IDLE", "duration_seconds": 14400},
        ]
        result = attach_reason(segments, device.id, db_session)
        assert all(s.get("reason") is None for s in result)

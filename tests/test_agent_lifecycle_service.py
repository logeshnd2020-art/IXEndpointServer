"""
7.8.0 -- AgentLifecycleService: batch ingestion, idempotency/replay,
dead-letter (batch-too-large) behavior. Server-side half of queue
persistence/replay/retry -- the client-side queue itself lives outside
this repository (see the implementation report).
"""
from datetime import datetime, timezone

import pytest

from app.models.agent_lifecycle_event import AgentLifecycleEvent
from app.schemas.agent_lifecycle import AgentLifecycleEventIn, AgentLifecycleSyncRequest
from app.services.agent_lifecycle_service import (
    MAX_EVENTS_PER_BATCH,
    AgentLifecycleService,
)


def utc(*a, **kw):
    return datetime(*a, tzinfo=timezone.utc, **kw)


def _event(event_uid, event_type="AGENT_STARTED", event_time=None, collected_at=None, **kw):
    return AgentLifecycleEventIn(
        event_uid=event_uid,
        event_type=event_type,
        event_time=event_time or utc(2026, 9, 7, 10, 0, 0),
        collected_at=collected_at or utc(2026, 9, 7, 10, 0, 1),
        **kw,
    )


class TestBasicIngestion:
    def test_single_event_is_stored(self, db_session, device):
        req = AgentLifecycleSyncRequest(events=[_event("uid-1")])
        resp = AgentLifecycleService.sync(db_session, req, device)

        assert resp.accepted_event_uids == ["uid-1"]
        rows = db_session.query(AgentLifecycleEvent).all()
        assert len(rows) == 1
        assert rows[0].event_uid == "uid-1"
        assert rows[0].device_id == device.id

    def test_upload_time_is_server_assigned_not_client_supplied(self, db_session, device):
        # AgentLifecycleEventIn has no upload_time field at all -- the
        # server sets it unconditionally at receipt.
        req = AgentLifecycleSyncRequest(events=[_event("uid-1")])
        AgentLifecycleService.sync(db_session, req, device)

        row = db_session.query(AgentLifecycleEvent).one()
        assert row.upload_time is not None

    def test_event_time_and_collected_at_preserved_exactly(self, db_session, device):
        et = utc(2026, 9, 1, 3, 0, 0)  # days before "now" -- simulates a
        ca = utc(2026, 9, 1, 3, 0, 2)  # replayed backlog after an outage
        req = AgentLifecycleSyncRequest(events=[_event("uid-1", event_time=et, collected_at=ca)])
        AgentLifecycleService.sync(db_session, req, device)

        row = db_session.query(AgentLifecycleEvent).one()
        # SQLite strips tzinfo on round-trip (the same well-documented
        # limitation worked around throughout this codebase) -- the
        # underlying wall-clock value is what must be preserved exactly,
        # not the Python tzinfo object attached to it.
        assert row.event_time.replace(tzinfo=timezone.utc) == et
        assert row.collected_at.replace(tzinfo=timezone.utc) == ca
        # upload_time must NOT be backdated to event_time -- it reflects
        # when THIS server actually received it.
        assert row.upload_time.replace(tzinfo=timezone.utc) != et


class TestIdempotencyAndReplay:
    def test_duplicate_event_uid_is_a_no_op(self, db_session, device):
        req = AgentLifecycleSyncRequest(events=[_event("uid-1")])
        AgentLifecycleService.sync(db_session, req, device)
        AgentLifecycleService.sync(db_session, req, device)  # retry/replay

        rows = db_session.query(AgentLifecycleEvent).filter_by(event_uid="uid-1").all()
        assert len(rows) == 1

    def test_replay_still_reports_the_event_uid_as_accepted(self, db_session, device):
        req = AgentLifecycleSyncRequest(events=[_event("uid-1")])
        AgentLifecycleService.sync(db_session, req, device)
        resp = AgentLifecycleService.sync(db_session, req, device)

        # A retried batch must still be told "this is safely stored,
        # prune it" -- even though it did nothing on the second call.
        assert resp.accepted_event_uids == ["uid-1"]

    def test_same_local_event_uid_on_different_devices_is_allowed(self, db_session, device):
        from app.models.device import Device

        other = Device(hostname="other", serial_number="SN-2", username="u", is_registered=True)
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        AgentLifecycleService.sync(db_session, AgentLifecycleSyncRequest(events=[_event("uid-1")]), device)
        AgentLifecycleService.sync(db_session, AgentLifecycleSyncRequest(events=[_event("uid-1")]), other)

        assert db_session.query(AgentLifecycleEvent).count() == 2

    def test_out_of_order_batch_is_stored_and_recoverable_by_event_time(self, db_session, device):
        # Simulates a backlog uploaded after a long outage, not
        # necessarily in chronological order.
        events = [
            _event("uid-3", event_time=utc(2026, 9, 7, 12, 0, 0)),
            _event("uid-1", event_time=utc(2026, 9, 7, 10, 0, 0)),
            _event("uid-2", event_time=utc(2026, 9, 7, 11, 0, 0)),
        ]
        AgentLifecycleService.sync(db_session, AgentLifecycleSyncRequest(events=events), device)

        from app.repositories.agent_lifecycle_repository import AgentLifecycleRepository
        rows = AgentLifecycleRepository.get_events_in_window(
            db_session, device.id, utc(2026, 9, 7, 0, 0, 0), utc(2026, 9, 7, 23, 59, 59)
        )
        assert [r.event_uid for r in rows] == ["uid-1", "uid-2", "uid-3"]


class TestDeadLetterBehavior:
    def test_oversized_batch_is_rejected_atomically(self, db_session, device):
        events = [_event(f"uid-{i}") for i in range(MAX_EVENTS_PER_BATCH + 1)]
        req = AgentLifecycleSyncRequest(events=events)

        with pytest.raises(ValueError):
            AgentLifecycleService.sync(db_session, req, device)

        # Nothing partially committed -- rejected before any insert.
        assert db_session.query(AgentLifecycleEvent).count() == 0

    def test_max_size_batch_is_accepted(self, db_session, device):
        events = [_event(f"uid-{i}") for i in range(MAX_EVENTS_PER_BATCH)]
        resp = AgentLifecycleService.sync(db_session, AgentLifecycleSyncRequest(events=events), device)
        assert len(resp.accepted_event_uids) == MAX_EVENTS_PER_BATCH

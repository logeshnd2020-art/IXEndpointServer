"""
Phase 3, Item 2 -- server lifecycle evidence.

Covers: the write path never raising even on DB failure, and the
conservative CONFIRMED / UNCERTAIN outage-evidence derivation described
in the Phase 3 design spec (Correction 2 / Rule 2).
"""
from datetime import datetime, timedelta, timezone

from app.models.server_lifecycle_event import ServerLifecycleEvent
from app.services.server_lifecycle_service import (
    get_outage_evidence,
    record_shutdown,
    record_startup,
)


def utc(*args, **kwargs):
    return datetime(*args, tzinfo=timezone.utc, **kwargs)


def _insert_event(db_session, event_type, occurred_at):
    event = ServerLifecycleEvent(event_type=event_type, occurred_at=occurred_at)
    db_session.add(event)
    db_session.commit()
    return event


class TestRecordStartupShutdown:
    def test_record_startup_writes_a_row(self, db_session):
        record_startup(db_session)

        rows = db_session.query(ServerLifecycleEvent).all()
        assert len(rows) == 1
        assert rows[0].event_type == "startup"
        assert rows[0].occurred_at is not None

    def test_record_shutdown_writes_a_row(self, db_session):
        record_shutdown(db_session)

        rows = db_session.query(ServerLifecycleEvent).all()
        assert len(rows) == 1
        assert rows[0].event_type == "shutdown"

    def test_record_startup_never_raises_on_db_failure(self, db_session):
        db_session.close()  # force any subsequent use to fail

        # Must not raise -- a failure to record evidence must never be
        # able to prevent the app from actually starting.
        record_startup(db_session)


class TestOutageEvidenceConfirmed:
    def test_shutdown_immediately_followed_by_startup_is_confirmed(self, db_session):
        _insert_event(db_session, "shutdown", utc(2026, 9, 7, 10, 0, 0))
        _insert_event(db_session, "startup", utc(2026, 9, 7, 10, 25, 0))

        evidence = get_outage_evidence(
            db_session, utc(2026, 9, 7, 9, 0, 0), utc(2026, 9, 7, 11, 0, 0)
        )

        assert len(evidence) == 1
        assert evidence[0].confidence == "CONFIRMED"
        assert evidence[0].start == utc(2026, 9, 7, 10, 0, 0)
        assert evidence[0].end == utc(2026, 9, 7, 10, 25, 0)


class TestOutageEvidenceUncertain:
    def test_two_startups_with_no_shutdown_between_is_uncertain_not_confirmed(
        self, db_session
    ):
        # Simulates a crash / hard reboot / power loss / SIGKILL -- no
        # shutdown row was ever written for the first run.
        _insert_event(db_session, "startup", utc(2026, 9, 7, 8, 0, 0))
        _insert_event(db_session, "startup", utc(2026, 9, 7, 9, 10, 0))

        evidence = get_outage_evidence(
            db_session, utc(2026, 9, 7, 7, 0, 0), utc(2026, 9, 7, 10, 0, 0)
        )

        assert len(evidence) == 1
        assert evidence[0].confidence == "UNCERTAIN"
        assert evidence[0].start == utc(2026, 9, 7, 8, 0, 0)
        assert evidence[0].end == utc(2026, 9, 7, 9, 10, 0)


class TestOutageEvidenceNoConclusionCases:
    def test_startup_followed_by_shutdown_is_not_outage_evidence(self, db_session):
        # A normal running span (startup -> shutdown) must never be
        # reported as any kind of outage evidence.
        _insert_event(db_session, "startup", utc(2026, 9, 7, 8, 0, 0))
        _insert_event(db_session, "shutdown", utc(2026, 9, 7, 18, 0, 0))

        evidence = get_outage_evidence(
            db_session, utc(2026, 9, 7, 7, 0, 0), utc(2026, 9, 7, 19, 0, 0)
        )

        assert evidence == []

    def test_no_events_at_all_yields_no_evidence_never_implies_available(
        self, db_session
    ):
        # Absence of any lifecycle row must never be treated as proof
        # the server was continuously available.
        evidence = get_outage_evidence(
            db_session, utc(2026, 9, 7, 0, 0, 0), utc(2026, 9, 7, 23, 59, 59)
        )

        assert evidence == []

    def test_intervals_outside_the_requested_window_are_excluded(self, db_session):
        _insert_event(db_session, "shutdown", utc(2026, 1, 1, 0, 0, 0))
        _insert_event(db_session, "startup", utc(2026, 1, 1, 1, 0, 0))

        evidence = get_outage_evidence(
            db_session, utc(2026, 9, 7, 0, 0, 0), utc(2026, 9, 7, 23, 59, 59)
        )

        assert evidence == []

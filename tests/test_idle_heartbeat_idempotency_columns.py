"""
Phase 3, Item 5 -- device_heartbeats.local_heartbeat_id (additive,
unconstrained) and idle_events(device_id, local_idle_id) uniqueness
(newly enforced, matching the existing sessions/applications pattern).
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.device_heartbeat import DeviceHeartbeat
from app.models.idle import IdleEvent
from app.models.session import Session as UserSession


def _make_session(db_session, device):
    session = UserSession(device_id=device.id, username="jdoe", status="ACTIVE")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


class TestHeartbeatLocalHeartbeatIdColumn:
    def test_null_local_heartbeat_id_is_accepted(self, db_session, device):
        heartbeat = DeviceHeartbeat(
            device_id=device.id,
            cpu_usage=1.0,
            memory_usage=1.0,
            disk_usage=1.0,
            battery_level=100,
            ip_address="127.0.0.1",
            uptime_seconds=10,
            local_heartbeat_id=None,
        )
        db_session.add(heartbeat)
        db_session.commit()

        assert heartbeat.id is not None
        assert heartbeat.local_heartbeat_id is None

    def test_duplicate_null_local_heartbeat_ids_are_accepted(self, db_session, device):
        # No uniqueness is enforced on this column yet (Phase 3, Item 5
        # scope) -- multiple NULLs, or even duplicate non-NULL values,
        # must not raise.
        for _ in range(2):
            db_session.add(
                DeviceHeartbeat(
                    device_id=device.id,
                    cpu_usage=1.0,
                    memory_usage=1.0,
                    disk_usage=1.0,
                    battery_level=100,
                    ip_address="127.0.0.1",
                    uptime_seconds=10,
                    local_heartbeat_id=None,
                )
            )
        db_session.commit()

        assert db_session.query(DeviceHeartbeat).count() == 2


class TestIdleEventsUniqueConstraint:
    def test_duplicate_device_and_local_idle_id_is_rejected(self, db_session, device):
        session = _make_session(db_session, device)

        db_session.add(
            IdleEvent(device_id=device.id, session_id=session.id, local_idle_id=42)
        )
        db_session.commit()

        db_session.add(
            IdleEvent(device_id=device.id, session_id=session.id, local_idle_id=42)
        )
        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    def test_same_local_idle_id_on_different_devices_is_allowed(self, db_session, device):
        from app.models.device import Device

        other_device = Device(
            hostname="other-mac",
            serial_number="SERIAL-0002",
            username="other",
            is_registered=True,
        )
        db_session.add(other_device)
        db_session.commit()
        db_session.refresh(other_device)

        session_a = _make_session(db_session, device)
        session_b = _make_session(db_session, other_device)

        db_session.add(
            IdleEvent(device_id=device.id, session_id=session_a.id, local_idle_id=7)
        )
        db_session.add(
            IdleEvent(
                device_id=other_device.id, session_id=session_b.id, local_idle_id=7
            )
        )
        db_session.commit()  # must not raise -- device_id is part of the key

        assert db_session.query(IdleEvent).count() == 2

    def test_null_local_idle_id_does_not_collide(self, db_session, device):
        session = _make_session(db_session, device)

        db_session.add(
            IdleEvent(device_id=device.id, session_id=session.id, local_idle_id=None)
        )
        db_session.add(
            IdleEvent(device_id=device.id, session_id=session.id, local_idle_id=None)
        )
        db_session.commit()  # SQL NULL never equals NULL -- must not raise

        assert db_session.query(IdleEvent).count() == 2

"""
Phase 3, Item 3 -- Device.is_online / staleness computed at read time.

Confirms the fix (staleness now actually resets) and, per Correction 3
/ Rule 3, that this module answers only the liveness/visibility
question -- it does not, and must not, ever assert a device-state or
infrastructure-state claim.
"""
from datetime import datetime, timedelta, timezone

from app.services.device_liveness_service import (
    STALE_THRESHOLD_SECONDS,
    is_stale,
    online_status_label,
)


def utc(*args, **kwargs):
    return datetime(*args, tzinfo=timezone.utc, **kwargs)


class TestIsStale:
    def test_recent_heartbeat_is_not_stale(self, db_session, device):
        now = utc(2026, 9, 7, 12, 0, 0)
        device.last_seen = now - timedelta(seconds=30)
        db_session.commit()

        assert is_stale(device, now=now) is False

    def test_heartbeat_older_than_threshold_is_stale(self, db_session, device):
        now = utc(2026, 9, 7, 12, 0, 0)
        device.last_seen = now - timedelta(seconds=STALE_THRESHOLD_SECONDS + 1)
        db_session.commit()

        assert is_stale(device, now=now) is True

    def test_heartbeat_exactly_at_threshold_is_not_yet_stale(self, db_session, device):
        now = utc(2026, 9, 7, 12, 0, 0)
        device.last_seen = now - timedelta(seconds=STALE_THRESHOLD_SECONDS)
        db_session.commit()

        assert is_stale(device, now=now) is False

    def test_missing_last_seen_fails_toward_stale(self, db_session, device):
        device.last_seen = None
        db_session.commit()

        assert is_stale(device, now=utc(2026, 9, 7, 12, 0, 0)) is True

    def test_naive_last_seen_is_treated_as_utc(self, db_session, device):
        # device.last_seen is always written as aware UTC by
        # AgentService; a naive value here can only be SQLite stripping
        # tzinfo on round-trip, so it must be re-tagged as UTC, not
        # local time.
        now = utc(2026, 9, 7, 12, 0, 0)
        device.last_seen = datetime(2026, 9, 7, 11, 59, 30)  # naive, 30s before `now`
        db_session.commit()

        assert is_stale(device, now=now) is False


class TestOnlineStatusLabel:
    def test_fresh_device_is_online(self, db_session, device):
        now = utc(2026, 9, 7, 12, 0, 0)
        device.last_seen = now - timedelta(seconds=10)
        db_session.commit()

        assert online_status_label(device, now=now) == "ONLINE"

    def test_stale_device_is_offline_even_if_is_online_flag_still_true(
        self, db_session, device
    ):
        # This is the exact bug being fixed: is_online never reset to
        # False anywhere in the pre-Phase-3 code. Confirm the computed
        # label ignores the stale flag and reports OFFLINE anyway.
        now = utc(2026, 9, 7, 12, 0, 0)
        device.is_online = True
        device.last_seen = now - timedelta(seconds=STALE_THRESHOLD_SECONDS + 1)
        db_session.commit()

        assert online_status_label(device, now=now) == "OFFLINE"

    def test_only_two_possible_values(self, db_session, device):
        now = utc(2026, 9, 7, 12, 0, 0)
        device.last_seen = now
        db_session.commit()
        assert online_status_label(device, now=now) in ("ONLINE", "OFFLINE")

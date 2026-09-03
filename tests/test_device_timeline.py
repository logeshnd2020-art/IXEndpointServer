from datetime import datetime

from app.models.session import Session

from tests.conftest import auth_headers


def _make_session(db_session, device, login, logout, local_session_id=1, status="LOGOUT"):
    session = Session(
        device_id=device.id,
        local_session_id=local_session_id,
        username="jdoe",
        login_time=login,
        logout_time=logout,
        status=status,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def test_day_timeline_fills_gaps_before_and_after_session_as_no_session(
    client, monitor_user, db_session, device
):
    # Session runs 10:00-14:00 on 2026-09-01 (a fully past day) -- the
    # rest of the day has no session at all and must show as NO_SESSION,
    # not be silently omitted or fabricated as some other type.
    _make_session(
        db_session,
        device,
        login=datetime(2026, 9, 1, 10, 0, 0),
        logout=datetime(2026, 9, 1, 14, 0, 0),
    )

    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get(
        "/api/device/%s/timeline?date=2026-09-01" % device.id, headers=headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["date"] == "2026-09-01"
    assert data["segments"], "expected a fully-covered day"

    total = sum(seg["duration_seconds"] for seg in data["segments"])
    assert total == 86400  # a full past day, always covered end-to-end

    no_session_total = sum(
        seg["duration_seconds"] for seg in data["segments"] if seg["type"] == "NO_SESSION"
    )
    # ~10h before login (00:00-10:00) + ~10h after logout (14:00-24:00).
    assert no_session_total == 20 * 3600

    # The segments must be contiguous and in order (no overlaps/gaps).
    for prev, nxt in zip(data["segments"], data["segments"][1:]):
        assert prev["end"] == nxt["start"]


def test_day_timeline_handles_multiple_sessions_same_day(client, monitor_user, db_session, device):
    _make_session(
        db_session, device,
        login=datetime(2026, 9, 1, 9, 0, 0),
        logout=datetime(2026, 9, 1, 11, 0, 0),
        local_session_id=1,
    )
    _make_session(
        db_session, device,
        login=datetime(2026, 9, 1, 15, 0, 0),
        logout=datetime(2026, 9, 1, 16, 0, 0),
        local_session_id=2,
    )

    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get(
        f"/api/device/{device.id}/timeline?date=2026-09-01", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    total = sum(seg["duration_seconds"] for seg in data["segments"])
    assert total == 86400


def test_day_timeline_invalid_date_returns_400(client, monitor_user, device):
    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get(
        f"/api/device/{device.id}/timeline?date=not-a-date", headers=headers
    )
    assert response.status_code == 400


def test_day_timeline_requires_auth(client, device):
    response = client.get(f"/api/device/{device.id}/timeline?date=2026-09-01")
    assert response.status_code == 401


def test_day_timeline_unknown_device_404(client, monitor_user):
    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get("/api/device/999999/timeline?date=2026-09-01", headers=headers)
    assert response.status_code == 404

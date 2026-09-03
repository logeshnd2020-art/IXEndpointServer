from app.models.application import Application
from app.models.session import Session

from tests.conftest import auth_headers, utc


def _make_active_session(db_session, device, local_session_id=1):
    session = Session(
        device_id=device.id,
        local_session_id=local_session_id,
        username="jdoe",
        login_time=utc(2026, 9, 1, 9, 0, 0),
        status="ACTIVE",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def test_current_application_returns_most_recent_even_if_closed(
    client, monitor_user, db_session, device
):
    session = _make_active_session(db_session, device)

    older = Application(
        device_id=device.id,
        session_id=session.id,
        application_name="Terminal",
        start_time=utc(2026, 9, 1, 9, 0, 0),
        end_time=utc(2026, 9, 1, 9, 5, 0),
    )
    newest = Application(
        device_id=device.id,
        session_id=session.id,
        application_name="Google Chrome",
        start_time=utc(2026, 9, 1, 9, 5, 0),
        end_time=utc(2026, 9, 1, 9, 10, 0),  # already closed, like the real agent reports
    )
    db_session.add_all([older, newest])
    db_session.commit()

    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get("/api/dashboard/current-applications", headers=headers)

    assert response.status_code == 200
    [entry] = response.json()
    assert entry["application"] == "Google Chrome"
    assert entry["is_currently_open"] is False


def test_current_application_marks_genuinely_open_app(
    client, monitor_user, db_session, device
):
    session = _make_active_session(db_session, device)

    app = Application(
        device_id=device.id,
        session_id=session.id,
        application_name="Xcode",
        start_time=utc(2026, 9, 1, 9, 0, 0),
        end_time=None,
    )
    db_session.add(app)
    db_session.commit()

    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get("/api/dashboard/current-applications", headers=headers)

    assert response.status_code == 200
    [entry] = response.json()
    assert entry["application"] == "Xcode"
    assert entry["is_currently_open"] is True


def test_current_application_empty_state_when_no_application_rows(
    client, monitor_user, db_session, device
):
    _make_active_session(db_session, device)

    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get("/api/dashboard/current-applications", headers=headers)

    assert response.status_code == 200
    assert response.json() == []

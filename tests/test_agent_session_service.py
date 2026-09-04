from app.services.agent_session_service import AgentSessionService
from app.schemas.agent_session import AgentSessionSyncRequest
from app.repositories.session_repository import SessionRepository

from tests.conftest import utc


def _request(**overrides):
    defaults = dict(
        local_session_id=1,
        username="jdoe",
        login_time=utc(2026, 9, 1, 9, 0, 0),
        logout_time=None,
        duration_seconds=None,
    )
    defaults.update(overrides)
    return AgentSessionSyncRequest(**defaults)


def test_create_persists_duration_seconds(db_session, device):
    request = _request(
        logout_time=utc(2026, 9, 1, 17, 0, 0),
        duration_seconds=25000,
    )

    response = AgentSessionService.sync(db_session, request, device)

    assert response.created is True

    session = SessionRepository.get_by_id(db_session, response.server_session_id)
    assert session.duration_seconds == 25000


def test_create_without_duration_stores_null(db_session, device):
    request = _request(duration_seconds=None)

    response = AgentSessionService.sync(db_session, request, device)

    session = SessionRepository.get_by_id(db_session, response.server_session_id)
    assert session.duration_seconds is None


def test_open_active_session_syncs_without_logout(db_session, device):
    request = _request(logout_time=None, duration_seconds=3600)

    response = AgentSessionService.sync(db_session, request, device)

    session = SessionRepository.get_by_id(db_session, response.server_session_id)
    assert session.status == "ACTIVE"
    assert session.logout_time is None
    assert session.duration_seconds == 3600


def test_update_existing_session_overwrites_duration(db_session, device):
    create_request = _request(duration_seconds=1000)
    AgentSessionService.sync(db_session, create_request, device)

    update_request = _request(
        logout_time=utc(2026, 9, 1, 17, 0, 0),
        duration_seconds=25200,
    )
    response = AgentSessionService.sync(db_session, update_request, device)

    assert response.created is False

    session = SessionRepository.get_by_id(db_session, response.server_session_id)
    assert session.duration_seconds == 25200
    assert session.status == "LOGOUT"


def test_update_with_null_duration_preserves_existing_value(db_session, device):
    create_request = _request(duration_seconds=18000)
    AgentSessionService.sync(db_session, create_request, device)

    # A later sync that omits duration_seconds must not erase the value
    # already recorded for this session.
    update_request = _request(
        logout_time=utc(2026, 9, 1, 17, 0, 0),
        duration_seconds=None,
    )
    response = AgentSessionService.sync(db_session, update_request, device)

    session = SessionRepository.get_by_id(db_session, response.server_session_id)
    assert session.duration_seconds == 18000
    assert session.status == "LOGOUT"


def test_update_preserves_duration_across_multiple_null_syncs(db_session, device):
    AgentSessionService.sync(db_session, _request(duration_seconds=500), device)
    AgentSessionService.sync(
        db_session,
        _request(login_time=utc(2026, 9, 1, 9, 5, 0), duration_seconds=None),
        device,
    )
    response = AgentSessionService.sync(
        db_session,
        _request(login_time=utc(2026, 9, 1, 9, 10, 0), duration_seconds=None),
        device,
    )

    session = SessionRepository.get_by_id(db_session, response.server_session_id)
    assert session.duration_seconds == 500

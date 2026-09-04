from app.schemas.heartbeat import AgentHeartbeatRequest
from app.services.agent_service import AgentService
from app.repositories.device_heartbeat_repository import DeviceHeartbeatRepository

from tests.conftest import TEST_MONITOR_PASSWORD, auth_headers


def _heartbeat_request(**overrides):
    defaults = dict(
        cpu_usage=15.0,
        memory_usage=42.0,
        disk_usage=55.0,
        battery_level=90,
        logged_in_user="jdoe",
        hostname="test-mac",
        ip_address="10.0.0.5",
        network_name="Office-WiFi",
        agent_version="7.7.8",
        uptime_seconds=3600,
    )
    defaults.update(overrides)
    return AgentHeartbeatRequest(**defaults)


def test_heartbeat_payload_without_mac_address_is_backward_compatible(db_session, device):
    # Simulates every heartbeat from the currently deployed agent, which
    # does not send mac_address at all -- the field must be optional and
    # must not break existing sync behavior.
    request = _heartbeat_request()

    AgentService.heartbeat(db_session, request, device)

    heartbeat = DeviceHeartbeatRepository.get_latest_heartbeat(db_session, device.id)
    assert heartbeat is not None
    assert heartbeat.mac_address is None
    # Existing fields are unaffected by this addition.
    assert heartbeat.ip_address == "10.0.0.5"
    assert heartbeat.uptime_seconds == 3600


def test_heartbeat_stores_reported_mac_address_unmodified(db_session, device):
    # The server must store exactly what the agent sends -- no
    # normalization, generation, or inference at the storage layer.
    request = _heartbeat_request(mac_address="ac:de:48:00:11:22")

    AgentService.heartbeat(db_session, request, device)

    heartbeat = DeviceHeartbeatRepository.get_latest_heartbeat(db_session, device.id)
    assert heartbeat.mac_address == "ac:de:48:00:11:22"


def test_health_api_exposes_mac_address_field(client, monitor_user, db_session, device):
    request = _heartbeat_request(mac_address="AC:DE:48:00:11:22")
    AgentService.heartbeat(db_session, request, device)

    headers = auth_headers(client, "monitor", TEST_MONITOR_PASSWORD)
    response = client.get(f"/api/device/{device.id}/health", headers=headers)

    assert response.status_code == 200
    assert response.json()["mac_address"] == "AC:DE:48:00:11:22"


def test_health_api_mac_address_is_none_when_agent_has_not_reported_one(
    client, monitor_user, db_session, device
):
    request = _heartbeat_request()  # no mac_address, matching real-world data today
    AgentService.heartbeat(db_session, request, device)

    headers = auth_headers(client, "monitor", TEST_MONITOR_PASSWORD)
    response = client.get(f"/api/device/{device.id}/health", headers=headers)

    assert response.status_code == 200
    assert response.json()["mac_address"] is None

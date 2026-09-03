from app.models.device_heartbeat import DeviceHeartbeat

from tests.conftest import auth_headers


def _make_heartbeat(db_session, device, uptime_seconds):
    heartbeat = DeviceHeartbeat(
        device_id=device.id,
        cpu_usage=12.5,
        memory_usage=64.0,
        disk_usage=40.0,
        battery_level=88,
        logged_in_user="jdoe",
        ip_address="192.168.1.50",
        network_name="Office-WiFi",
        uptime_seconds=uptime_seconds,
    )
    db_session.add(heartbeat)
    db_session.commit()
    db_session.refresh(heartbeat)
    return heartbeat


def test_health_requires_auth(client, device):
    response = client.get(f"/api/device/{device.id}/health")
    assert response.status_code == 401


def test_health_uptime_seconds_is_the_agent_reported_value_unmodified(
    client, monitor_user, db_session, device
):
    # 3 days 7 hours 24 minutes, chosen to be inconsistent with any
    # login-time/heartbeat-gap/server-clock arithmetic for this test's
    # session-less device -- proving the value returned is exactly what
    # was stored from the agent's own heartbeat payload, not derived from
    # anything else.
    reported_uptime = (3 * 86400) + (7 * 3600) + (24 * 60)
    _make_heartbeat(db_session, device, uptime_seconds=reported_uptime)

    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get(f"/api/device/{device.id}/health", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["uptime_seconds"] == reported_uptime


def test_health_response_never_fabricates_a_mac_address(
    client, monitor_user, db_session, device
):
    # device_heartbeats.mac_address exists as a real, agent-reportable
    # field now, but no currently deployed agent sends one -- a heartbeat
    # that doesn't report it must come back as None, never an invented
    # value. (See tests/test_agent_heartbeat_mac_address.py for the
    # round-trip case where a mac_address IS reported.)
    _make_heartbeat(db_session, device, uptime_seconds=100)

    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")
    response = client.get(f"/api/device/{device.id}/health", headers=headers)

    assert response.status_code == 200
    assert response.json()["mac_address"] is None

    # /api/device/{id} (device header) deliberately has no mac_address
    # field at all -- MAC data lives on the heartbeat, not the device
    # record, so there's nothing to assert null here beyond its absence.
    device_response = client.get(f"/api/device/{device.id}", headers=headers)
    assert device_response.status_code == 200
    assert "mac_address" not in device_response.json()


def test_device_health_endpoints_still_work_for_mac_health_tab(
    client, monitor_user, db_session, device
):
    _make_heartbeat(db_session, device, uptime_seconds=3600)
    headers = auth_headers(client, "monitor", "REDACTED-ROTATED-CREDENTIAL")

    for path in (
        f"/api/device/{device.id}",
        f"/api/device/{device.id}/health",
        f"/api/device/{device.id}/installed-applications",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, f"{path} -> {response.status_code}"

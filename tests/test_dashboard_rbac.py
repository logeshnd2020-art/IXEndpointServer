from tests.conftest import TEST_MONITOR_PASSWORD, auth_headers


def test_anonymous_request_is_unauthorized(client):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 401


def test_monitor_can_login_and_view_dashboard(client, monitor_user):
    headers = auth_headers(client, "monitor", TEST_MONITOR_PASSWORD)

    response = client.get("/api/dashboard/summary", headers=headers)
    assert response.status_code == 200

    for endpoint in (
        "/api/dashboard/live-devices",
        "/api/dashboard/current-applications",
        "/api/dashboard/productivity",
    ):
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 200, f"{endpoint} -> {response.status_code}"


def test_login_response_includes_role(client, monitor_user):
    response = client.post(
        "/api/auth/login",
        json={"username_or_email": "monitor", "password": TEST_MONITOR_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "MONITOR"


def test_monitor_can_view_device_detail_endpoints(client, monitor_user, device):
    headers = auth_headers(client, "monitor", TEST_MONITOR_PASSWORD)

    response = client.get(f"/api/device/{device.id}", headers=headers)
    assert response.status_code == 200

    response = client.get(f"/api/device/{device.id}/timeline", headers=headers)
    assert response.status_code in (200, 404)  # 404 only if no session exists yet

    response = client.get(
        f"/api/device/{device.id}/installed-applications", headers=headers
    )
    assert response.status_code == 200


def test_monitor_cannot_create_device(client, monitor_user):
    headers = auth_headers(client, "monitor", TEST_MONITOR_PASSWORD)

    response = client.post(
        "/api/devices",
        headers=headers,
        json={
            "device_uuid": "should-not-be-created",
            "hostname": "IXMAC999",
            "serial_number": "SERIAL-999",
            "username": "nobody",
        },
    )
    assert response.status_code == 403


def test_monitor_cannot_update_or_delete_device(client, monitor_user, device):
    headers = auth_headers(client, "monitor", TEST_MONITOR_PASSWORD)

    response = client.put(
        f"/api/devices/{device.id}",
        headers=headers,
        json={"hostname": "renamed"},
    )
    assert response.status_code == 403

    response = client.delete(f"/api/devices/{device.id}", headers=headers)
    assert response.status_code == 403


def test_monitor_cannot_manage_enrollment_keys(client, monitor_user):
    headers = auth_headers(client, "monitor", TEST_MONITOR_PASSWORD)

    response = client.post(
        "/api/admin/enrollment-keys/",
        headers=headers,
        json={"description": "should not be allowed"},
    )
    assert response.status_code == 403

    response = client.get("/api/admin/enrollment-keys/", headers=headers)
    assert response.status_code == 403

    response = client.delete("/api/admin/enrollment-keys/1", headers=headers)
    assert response.status_code == 403


def test_admin_retains_full_access(client, admin_user, device):
    headers = auth_headers(client, "admin", "REDACTED-ROTATED-CREDENTIAL")

    response = client.get("/api/dashboard/summary", headers=headers)
    assert response.status_code == 200

    response = client.get("/api/devices", headers=headers)
    assert response.status_code == 200

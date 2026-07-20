from services.inventory_service import update_inventory
from services.application_service import sync_applications
from database import get_connection


def register_device(data):

    conn = get_connection()
    cur = conn.cursor()

    hostname = data.get("hostname")

    cur.execute(
        """
        SELECT DeviceID
        FROM Devices
        WHERE Hostname=?
        """,
        (hostname,)
    )

    device = cur.fetchone()

    if device:

        cur.execute(
            """
            UPDATE Devices
            SET
                Username=?,
                Serial=?,
                Model=?,
                OSVersion=?,
                IPAddress=?,
                AgentVersion=?,
                LastSeen=CURRENT_TIMESTAMP,
                Status='Online'
            WHERE Hostname=?
            """,
            (
                data.get("username"),
                data.get("serial"),
                data.get("model"),
                data.get("os"),
                data.get("ip"),
                data.get("agent_version"),
                hostname
            )
        )

    else:

        cur.execute(
            """
            INSERT INTO Devices
            (
                Hostname,
                Username,
                Serial,
                Model,
                OSVersion,
                IPAddress,
                AgentVersion,
                Status
            )
            VALUES
            (
                ?,?,?,?,?,?,?,?
            )
            """,
            (
                hostname,
                data.get("username"),
                data.get("serial"),
                data.get("model"),
                data.get("os"),
                data.get("ip"),
                data.get("agent_version"),
                "Online"
            )
        )

    conn.commit()

    conn.close()

    return {
        "status": "success",
        "hostname": hostname
    }
def checkin_device(data):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE Devices
        SET
            CPU=?,
            Memory=?,
            Disk=?,
            LastSeen=CURRENT_TIMESTAMP,
            Status='Online'
        WHERE Hostname=?
        """,
        (
            data.get("cpu"),
            data.get("memory"),
            data.get("disk"),
            data.get("hostname")
        )
    )

    conn.commit()
    conn.close()

    return {
        "status": "heartbeat received",
        "hostname": data.get("hostname")
    }
def inventory_sync(data):

    serial = data.get("serial")

    inventory = data.get("inventory")

    success = update_inventory(
        serial,
        inventory
    )

    return {
        "status": "success" if success else "failed"
    }
def application_sync(data):

    success = sync_applications(
        data.get("serial"),
        data.get("applications", [])
    )

    return {
        "status": "success" if success else "failed"
    }

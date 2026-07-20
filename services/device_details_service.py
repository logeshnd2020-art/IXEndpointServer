from database import get_connection


def get_device_details(device_id):

    conn = get_connection()
    cur = conn.cursor()

    # Device
    cur.execute(
        "SELECT * FROM Devices WHERE DeviceID=?",
        (device_id,)
    )

    device = cur.fetchone()

    # Inventory
    cur.execute(
        "SELECT * FROM Inventory WHERE DeviceID=?",
        (device_id,)
    )

    inventory = cur.fetchone()

    # Applications
    cur.execute(
        """
        SELECT
            AppName,
            Version,
            BundleID
        FROM Applications
        WHERE DeviceID=?
        ORDER BY AppName
        """,
        (device_id,)
    )

    applications = cur.fetchall()

    conn.close()

    return {
        "device": device,
        "inventory": inventory,
        "applications": applications
    }

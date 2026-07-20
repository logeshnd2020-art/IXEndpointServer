from database import get_connection


def sync_applications(device_serial, applications):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT DeviceID
        FROM Devices
        WHERE Serial=?
        """,
        (device_serial,)
    )

    device = cur.fetchone()

    if not device:
        conn.close()
        return False

    device_id = device["DeviceID"]

    cur.execute(
        "DELETE FROM Applications WHERE DeviceID=?",
        (device_id,)
    )

    for app in applications:

        cur.execute(
            """
            INSERT INTO Applications
            (
                DeviceID,
                AppName,
                Version,
                BundleID,
                InstallPath
            )
            VALUES
            (
                ?,?,?,?,?
            )
            """,
            (
                device_id,
                app.get("name"),
                app.get("version"),
                app.get("bundle"),
                app.get("path")
            )
        )

    conn.commit()
    conn.close()

    return True

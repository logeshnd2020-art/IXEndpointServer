from database import get_connection


def update_inventory(device_serial, inventory):

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
        """
        SELECT InventoryID
        FROM Inventory
        WHERE DeviceID=?
        """,
        (device_id,)
    )

    existing = cur.fetchone()

    if existing:

        cur.execute(
            """
            UPDATE Inventory
            SET
                Model=?,
                ModelIdentifier=?,
                CPUModel=?,
                MemoryInstalled=?,
                DiskSize=?,
                OSVersion=?,
                BuildVersion=?,
                Architecture=?,
                MACAddress=?,
                Gateway=?,
                DNS=?,
                WiFiSSID=?,
                FileVault=?,
                Firewall=?,
                Gatekeeper=?,
                SIP=?,
                LastInventorySync=CURRENT_TIMESTAMP
            WHERE DeviceID=?
            """,
            (
                inventory["model"],
                inventory["model_identifier"],
                inventory["cpu"],
                inventory["memory"],
                inventory["disk"],
                inventory["os"],
                inventory["build"],
                inventory["architecture"],
                inventory["mac"],
                inventory["gateway"],
                inventory["dns"],
                inventory["wifi"],
                inventory["filevault"],
                inventory["firewall"],
                inventory["gatekeeper"],
                inventory["sip"],
                device_id
            )
        )

    else:

        cur.execute(
            """
            INSERT INTO Inventory
            (
                DeviceID,
                Model,
                ModelIdentifier,
                CPUModel,
                MemoryInstalled,
                DiskSize,
                OSVersion,
                BuildVersion,
                Architecture,
                MACAddress,
                Gateway,
                DNS,
                WiFiSSID,
                FileVault,
                Firewall,
                Gatekeeper,
                SIP
            )
            VALUES
            (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,
            (
                device_id,
                inventory["model"],
                inventory["model_identifier"],
                inventory["cpu"],
                inventory["memory"],
                inventory["disk"],
                inventory["os"],
                inventory["build"],
                inventory["architecture"],
                inventory["mac"],
                inventory["gateway"],
                inventory["dns"],
                inventory["wifi"],
                inventory["filevault"],
                inventory["firewall"],
                inventory["gatekeeper"],
                inventory["sip"]
            )
        )

    conn.commit()
    conn.close()

    return True

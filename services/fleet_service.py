from database import get_connection


def get_all_devices():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            DeviceID,
            Hostname,
            Username,
            Model,
            OSVersion,
            IPAddress,
            AgentVersion,
            LastSeen,
            Status
        FROM Devices
        ORDER BY Hostname;
    """)

    devices = cur.fetchall()

    conn.close()

    return devices

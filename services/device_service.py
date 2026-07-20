from database import get_connection


def get_device(device_id):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM Devices
        WHERE DeviceID=?
    """, (device_id,))

    device = cur.fetchone()

    conn.close()

    return device

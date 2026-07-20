from database import get_connection


def activity_sync(data):

    conn = get_connection()
    cur = conn.cursor()

    serial = data.get("serial")
    events = data.get("events", [])

    cur.execute(
        "SELECT DeviceID, Username FROM Devices WHERE Serial=?",
        (serial,)
    )

    device = cur.fetchone()

    if not device:
        conn.close()
        return {
            "status": "failed",
            "message": "Device not found"
        }

    device_id = device["DeviceID"]
    username = device["Username"]

    for event in events:

        cur.execute(
            """
            INSERT INTO ActivityEvents
            (
                DeviceID,
                Username,
                EventType,
                EventName,
                EventValue,
                EventTime
            )
            VALUES
            (
                ?,?,?,?,?,?
            )
            """,
            (
                device_id,
                username,
                event.get("type"),
                event.get("name"),
                event.get("value"),
                event.get("event_time")
            )
        )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "events_received": len(events)
    }

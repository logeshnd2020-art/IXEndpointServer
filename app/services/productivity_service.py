from sqlalchemy import func

from app.models.device import Device
from app.models.session import Session
from app.models.idle import IdleEvent
from app.models.activity import ActivityEvent


class ProductivityService:

    @staticmethod
    def get_productivity(db):

        devices = db.query(Device).all()

        results = []

        for device in devices:

            session = (
                db.query(Session)
                .filter(
                    Session.device_id == device.id,
                    Session.status == "ACTIVE",
                )
                .first()
            )

            if not session:
                continue

            idle_seconds = (
                db.query(func.coalesce(func.sum(IdleEvent.idle_seconds), 0))
                .filter(IdleEvent.session_id == session.id)
                .scalar()
            )

            mouse_clicks = (
                db.query(func.coalesce(func.sum(ActivityEvent.mouse_clicks), 0))
                .filter(ActivityEvent.session_id == session.id)
                .scalar()
            )

            keyboard_hits = (
                db.query(func.coalesce(func.sum(ActivityEvent.keyboard_hits), 0))
                .filter(ActivityEvent.session_id == session.id)
                .scalar()
            )

            working_seconds = 28800  # Temporary: 8 hours
            active_seconds = max(working_seconds - idle_seconds, 0)

            productivity = (
                round((active_seconds / working_seconds) * 100, 2)
                if working_seconds > 0
                else 0
            )

            results.append(
                {
                    "hostname": device.hostname,
                    "username": session.username,
                    "working_seconds": working_seconds,
                    "idle_seconds": idle_seconds,
                    "active_seconds": active_seconds,
                    "productivity_percent": productivity,
                    "mouse_clicks": mouse_clicks,
                    "keyboard_hits": keyboard_hits,
                }
            )

        return results

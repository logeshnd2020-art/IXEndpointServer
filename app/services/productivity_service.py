from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.models.device import Device
from app.models.session import Session
from app.models.idle import IdleEvent
from app.models.activity import ActivityEvent
from app.models.application import Application


CLIENT_LOCAL_TZ = ZoneInfo("Asia/Kolkata")


class ProductivityService:

    @staticmethod
    def _normalize(dt):
        # Database timestamps are stored as naive endpoint-local time (IST).
        # Convert them to UTC so all calculations use one time frame.
        if dt is None:
            return None

        if dt.tzinfo is None:
            return dt.replace(
                tzinfo=CLIENT_LOCAL_TZ
            ).astimezone(timezone.utc)

        return dt.astimezone(timezone.utc)

    @staticmethod
    def _overlap_seconds(start1, end1, start2, end2):
        """
        Return the number of seconds where two time intervals overlap.
        """
        start1 = ProductivityService._normalize(start1)
        end1 = ProductivityService._normalize(end1)
        start2 = ProductivityService._normalize(start2)
        end2 = ProductivityService._normalize(end2)

        if not start1 or not start2:
            return 0

        if end1 is None:
            end1 = datetime.now(timezone.utc)

        if end2 is None:
            end2 = datetime.now(timezone.utc)

        start = max(start1, start2)
        end = min(end1, end2)

        if end <= start:
            return 0

        return int((end - start).total_seconds())

    @staticmethod
    def _effective_working_seconds(session, wall_clock_seconds):
        """
        Prefer the agent-reported monitored-awake duration (wall time
        minus confirmed sleep minus unknown gaps) over raw wall-clock
        session time, which would otherwise include macOS sleep.

        Clamped to [0, wall_clock_seconds] so a bad/stale duration value
        can never inflate working time beyond what the session's own
        login/logout timestamps allow.
        """
        duration_seconds = session.duration_seconds

        if duration_seconds is None:
            return wall_clock_seconds

        return max(
            0,
            min(duration_seconds, wall_clock_seconds),
        )

    @staticmethod
    def get_productivity(db: DBSession):

        devices = db.query(Device).all()

        results = []

        now = datetime.now(timezone.utc)

        for device in devices:

            # ----------------------------------------
            # Current active session
            # ----------------------------------------

            session = (
                db.query(Session)
                .filter(
                    Session.device_id == device.id,
                    Session.status == "ACTIVE",
                )
                .order_by(Session.login_time.desc())
                .first()
            )

            if not session:
                continue

            login_time = session.login_time

            if login_time is None:
                continue

            login_time = ProductivityService._normalize(login_time)

            logout_time = (
                ProductivityService._normalize(session.logout_time)
                if session.logout_time
                else now
            )

            # ----------------------------------------
            # Session elapsed time
            # ----------------------------------------

            wall_clock_seconds = max(
                int((logout_time - login_time).total_seconds()),
                0,
            )

            working_seconds = (
                ProductivityService._effective_working_seconds(
                    session,
                    wall_clock_seconds,
                )
            )

            # ----------------------------------------
            # Idle events
            # ----------------------------------------

            idle_events = (
                db.query(IdleEvent)
                .filter(
                    IdleEvent.session_id == session.id,
                )
                .order_by(
                    IdleEvent.idle_start.asc()
                )
                .all()
            )

            idle_seconds = 0

            for idle in idle_events:

                idle_start = ProductivityService._normalize(
                    idle.idle_start
                )

                idle_end = (
                    ProductivityService._normalize(
                        idle.idle_end
                    )
                    if idle.idle_end
                    else now
                )

                idle_seconds += ProductivityService._overlap_seconds(
                    login_time,
                    logout_time,
                    idle_start,
                    idle_end,
                )

            idle_seconds = min(
                idle_seconds,
                working_seconds,
            )

            active_seconds = max(
                working_seconds - idle_seconds,
                0,
            )

            productivity = (
                round(
                    (active_seconds / working_seconds) * 100,
                    2,
                )
                if working_seconds > 0
                else 0
            )

            # ----------------------------------------
            # Activity metrics
            # ----------------------------------------

            mouse_clicks = (
                db.query(
                    func.coalesce(
                        func.sum(
                            ActivityEvent.mouse_clicks
                        ),
                        0,
                    )
                )
                .filter(
                    ActivityEvent.session_id == session.id,
                )
                .scalar()
            )

            keyboard_hits = (
                db.query(
                    func.coalesce(
                        func.sum(
                            ActivityEvent.keyboard_hits
                        ),
                        0,
                    )
                )
                .filter(
                    ActivityEvent.session_id == session.id,
                )
                .scalar()
            )

            mouse_clicks = int(mouse_clicks or 0)
            keyboard_hits = int(keyboard_hits or 0)

            # ----------------------------------------
            # Application active-time calculation
            # ----------------------------------------

            applications = (
                db.query(Application)
                .filter(
                    Application.device_id == device.id,
                    Application.session_id == session.id,
                )
                .order_by(
                    Application.start_time.asc()
                )
                .all()
            )

            application_totals = {}

            for app in applications:

                app_start = ProductivityService._normalize(
                    app.start_time
                )

                app_end = (
                    ProductivityService._normalize(
                        app.end_time
                    )
                    if app.end_time
                    else now
                )

                if not app_start:
                    continue

                if app_end < app_start:
                    continue

                elapsed_seconds = int(
                    (app_end - app_start).total_seconds()
                )

                # An application cannot have been active longer than the
                # session's own monitored-awake duration.
                elapsed_seconds = min(
                    elapsed_seconds,
                    working_seconds,
                )

                # ----------------------------------------
                # Idle time overlapping this application
                # ----------------------------------------

                app_idle_seconds = 0

                for idle in idle_events:

                    idle_start = ProductivityService._normalize(
                        idle.idle_start
                    )

                    idle_end = (
                        ProductivityService._normalize(
                            idle.idle_end
                        )
                        if idle.idle_end
                        else now
                    )

                    app_idle_seconds += (
                        ProductivityService._overlap_seconds(
                            app_start,
                            app_end,
                            idle_start,
                            idle_end,
                        )
                    )

                app_idle_seconds = min(
                    app_idle_seconds,
                    elapsed_seconds,
                )

                app_active_seconds = max(
                    elapsed_seconds - app_idle_seconds,
                    0,
                )

                name = app.application_name or "Unknown"

                if name not in application_totals:

                    application_totals[name] = {
                        "application": name,
                        "elapsed_seconds": 0,
                        "idle_seconds": 0,
                        "active_seconds": 0,
                    }

                application_totals[name][
                    "elapsed_seconds"
                ] += elapsed_seconds

                application_totals[name][
                    "idle_seconds"
                ] += app_idle_seconds

                application_totals[name][
                    "active_seconds"
                ] += app_active_seconds

            # ----------------------------------------
            # Sort applications by active time
            # ----------------------------------------

            application_usage = sorted(
                application_totals.values(),
                key=lambda x: x["active_seconds"],
                reverse=True,
            )

            # ----------------------------------------
            # Result
            # ----------------------------------------

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

                    "applications": application_usage,
                }
            )

        return results

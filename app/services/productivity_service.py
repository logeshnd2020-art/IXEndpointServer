from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.models.device import Device
from app.models.session import Session
from app.models.activity import ActivityEvent
from app.models.application import Application
from app.services.timeline_service import TimelineService


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

            # Canonical interval representation -- the single source of
            # truth for ACTIVE/IDLE/SLEEP_GAP, shared with
            # ProductivityReportService and the Activity Timeline/Activity
            # Details UI (TimelineService.build()). Deliberately does not
            # use session.duration_seconds -- see TimelineService's
            # docstring for why that field isn't treated as authoritative.
            segments = TimelineService.build(
                db,
                session,
                login_time,
                logout_time,
            )

            segment_totals = TimelineService.totals_by_type(segments)

            active_seconds = segment_totals.get("ACTIVE", 0)
            idle_seconds = segment_totals.get("IDLE", 0)
            working_seconds = active_seconds + idle_seconds

            # Sleep/unknown-gap time is simply whatever was excluded from
            # monitored (working) time -- no separate accounting model,
            # just the SLEEP_GAP segments' own total.
            sleep_seconds = segment_totals.get("SLEEP_GAP", 0)

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

                # Scope this application's usage span to the same
                # canonical ACTIVE/IDLE/SLEEP_GAP segments the session
                # totals use, so an app is never credited with active or
                # idle time during a stretch the device wasn't even being
                # observed (SLEEP_GAP overlap is simply excluded, the same
                # way session-level working_seconds excludes it).
                app_by_type = TimelineService.overlap_seconds_by_type(
                    segments,
                    app_start,
                    app_end,
                )

                app_active_seconds = app_by_type.get("ACTIVE", 0)
                app_idle_seconds = app_by_type.get("IDLE", 0)
                elapsed_seconds = app_active_seconds + app_idle_seconds

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
                key=lambda x: x["elapsed_seconds"],
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
                    "sleep_seconds": sleep_seconds,

                    "productivity_percent": productivity,

                    "mouse_clicks": mouse_clicks,
                    "keyboard_hits": keyboard_hits,

                    "applications": application_usage,
                }
            )

        return results

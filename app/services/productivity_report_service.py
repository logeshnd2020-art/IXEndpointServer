from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from app.models.device import Device
from app.models.session import Session
from app.models.application import Application
from app.services.timeline_service import TimelineService


LOCAL_TZ = ZoneInfo("Asia/Kolkata")


class ProductivityReportService:

    @staticmethod
    def normalize(dt):
        if dt is None:
            return None

        if dt.tzinfo is None:
            return dt.replace(
                tzinfo=LOCAL_TZ
            ).astimezone(timezone.utc)

        return dt.astimezone(timezone.utc)

    @staticmethod
    def build_periods(
        report_type,
        start_date,
        end_date,
    ):

        periods = []

        if report_type == "daily":

            current = start_date

            while current <= end_date:

                next_day = current + timedelta(days=1)

                periods.append(
                    (
                        current,
                        next_day,
                    )
                )

                current = next_day

        elif report_type == "weekly":

            current = start_date

            while current <= end_date:

                next_week = current + timedelta(days=7)

                periods.append(
                    (
                        current,
                        next_week,
                    )
                )

                current = next_week

        elif report_type == "monthly":

            current = start_date.replace(day=1)

            while current <= end_date:

                if current.month == 12:
                    next_month = current.replace(
                        year=current.year + 1,
                        month=1,
                        day=1,
                    )
                else:
                    next_month = current.replace(
                        month=current.month + 1,
                        day=1,
                    )

                periods.append(
                    (
                        current,
                        next_month,
                    )
                )

                current = next_month

        else:
            raise ValueError(
                "report_type must be daily, weekly or monthly"
            )

        return periods

    @staticmethod
    def get_reports(
        db: DBSession,
        report_type="daily",
        start_date=None,
        end_date=None,
        device_id=None,
    ):

        today = datetime.now(
            LOCAL_TZ
        ).date()

        start_date = start_date or today
        end_date = end_date or start_date

        periods = (
            ProductivityReportService.build_periods(
                report_type,
                start_date,
                end_date,
            )
        )

        devices_query = db.query(Device)

        if device_id is not None:
            devices_query = devices_query.filter(
                Device.id == device_id
            )

        devices = devices_query.all()

        results = []

        now_utc = datetime.now(
            timezone.utc
        )

        for period_start_date, period_end_date in periods:

            period_start_local = datetime.combine(
                period_start_date,
                datetime.min.time(),
            ).replace(
                tzinfo=LOCAL_TZ
            )

            period_end_local = datetime.combine(
                period_end_date,
                datetime.min.time(),
            ).replace(
                tzinfo=LOCAL_TZ
            )

            period_start_utc = (
                period_start_local.astimezone(
                    timezone.utc
                )
            )

            period_end_utc = (
                period_end_local.astimezone(
                    timezone.utc
                )
            )

            for device in devices:

                sessions = (
                    db.query(Session)
                    .filter(
                        Session.device_id == device.id
                    )
                    .all()
                )

                # ------------------------------------------------
                # ONE aggregate per host + user + reporting period
                # ------------------------------------------------

                user_totals = {}

                for session in sessions:

                    if not session.login_time:
                        continue

                    session_start = (
                        ProductivityReportService.normalize(
                            session.login_time
                        )
                    )

                    session_end = (
                        ProductivityReportService.normalize(
                            session.logout_time
                        )
                        if session.logout_time
                        else now_utc
                    )

                    overlap_start = max(
                        session_start,
                        period_start_utc,
                    )

                    overlap_end = min(
                        session_end,
                        period_end_utc,
                    )

                    if overlap_end <= overlap_start:
                        continue

                    username = (
                        session.username
                        or "Unknown"
                    )

                    if username not in user_totals:

                        user_totals[username] = {
                            "working_seconds": 0,
                            "idle_seconds": 0,
                            # SLEEP_CONFIRMED total only -- see
                            # ProductivityService for why this is
                            # deliberately not "every kind of unobserved
                            # time". Always 0 today (no sleep-evidence
                            # signal exists yet).
                            "sleep_seconds": 0,
                            "monitoring_gap_seconds": 0,
                            "off_session_seconds": 0,
                            "applications": {},
                        }

                    aggregate = user_totals[
                        username
                    ]

                    # ------------------------------------------------
                    # Working time for this reporting period
                    #
                    # A session can span midnight / multiple days. For a
                    # daily report, count only the portion of the session
                    # that falls inside this day -- via the same canonical
                    # interval representation used everywhere else
                    # (TimelineService.build(), scoped to this period's
                    # overlap window). Deliberately does not use
                    # session.duration_seconds; see TimelineService's
                    # docstring for why.
                    # ------------------------------------------------
                    segments = TimelineService.build(
                        db,
                        session,
                        overlap_start,
                        overlap_end,
                    )

                    segment_totals = TimelineService.totals_by_type(segments)

                    session_idle = segment_totals.get("IDLE", 0)
                    working_seconds = segment_totals.get("ACTIVE", 0) + session_idle

                    aggregate[
                        "working_seconds"
                    ] += working_seconds

                    aggregate[
                        "sleep_seconds"
                    ] += segment_totals.get("SLEEP_CONFIRMED", 0)

                    aggregate[
                        "monitoring_gap_seconds"
                    ] += segment_totals.get("MONITORING_GAP", 0)

                    aggregate[
                        "off_session_seconds"
                    ] += segment_totals.get("OFF_SESSION", 0)

                    aggregate[
                        "idle_seconds"
                    ] += session_idle

                    applications = (
                        db.query(Application)
                        .filter(
                            Application.session_id
                            == session.id
                        )
                        .all()
                    )

                    for app in applications:

                        app_start = (
                            ProductivityReportService.normalize(
                                app.start_time
                            )
                        )

                        app_end = (
                            ProductivityReportService.normalize(
                                app.end_time
                            )
                            if app.end_time
                            else now_utc
                        )

                        if not app_start:
                            continue

                        app_start = max(
                            app_start,
                            overlap_start,
                            period_start_utc,
                        )

                        app_end = min(
                            app_end,
                            overlap_end,
                            period_end_utc,
                        )

                        if app_end <= app_start:
                            continue

                        # Scope this application's usage span to the same
                        # canonical ACTIVE/IDLE/SLEEP_GAP segments the
                        # session totals above use, so app-level numbers
                        # can never disagree with the session/day totals
                        # they're supposed to sum up to. SLEEP_GAP overlap
                        # is simply excluded from elapsed entirely, the
                        # same way session-level working_seconds excludes
                        # it -- an app can't have been "active" or "idle"
                        # during a stretch the device wasn't observed.
                        app_by_type = TimelineService.overlap_seconds_by_type(
                            segments,
                            app_start,
                            app_end,
                        )

                        app_active = app_by_type.get("ACTIVE", 0)
                        app_idle = app_by_type.get("IDLE", 0)
                        elapsed = app_active + app_idle

                        name = (
                            app.application_name
                            or "Unknown"
                        )

                        if name not in aggregate[
                            "applications"
                        ]:

                            aggregate[
                                "applications"
                            ][name] = {
                                "application": name,
                                "elapsed_seconds": 0,
                                "idle_seconds": 0,
                                "active_seconds": 0,
                            }

                        app_total = aggregate[
                            "applications"
                        ][name]

                        app_total[
                            "elapsed_seconds"
                        ] += elapsed

                        app_total[
                            "idle_seconds"
                        ] += app_idle

                        app_total[
                            "active_seconds"
                        ] += app_active

                # ------------------------------------------------
                # FINAL REPORT
                # ------------------------------------------------

                for username, aggregate in (
                    user_totals.items()
                ):

                    working = aggregate[
                        "working_seconds"
                    ]

                    idle = min(
                        aggregate["idle_seconds"],
                        working,
                    )

                    active = max(
                        working - idle,
                        0,
                    )

                    productivity = (
                        round(
                            active
                            / working
                            * 100,
                            2,
                        )
                        if working > 0
                        else 0
                    )

                    application_usage = sorted(
                        aggregate[
                            "applications"
                        ].values(),
                        key=lambda x:
                            x["active_seconds"],
                        reverse=True,
                    )

                    results.append(
                        {
                            "hostname":
                                device.hostname,

                            "username":
                                username,

                            "period_start":
                                period_start_date.isoformat(),

                            "period_end":
                                (
                                    period_end_date
                                    - timedelta(days=1)
                                ).isoformat(),

                            "working_seconds":
                                working,

                            "idle_seconds":
                                idle,

                            "active_seconds":
                                active,

                            "sleep_seconds":
                                aggregate["sleep_seconds"],

                            "monitoring_gap_seconds":
                                aggregate["monitoring_gap_seconds"],

                            "off_session_seconds":
                                aggregate["off_session_seconds"],

                            "productivity_percent":
                                productivity,

                            "applications":
                                application_usage,
                        }
                    )

        return results

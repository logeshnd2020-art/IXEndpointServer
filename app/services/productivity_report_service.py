from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from app.models.device import Device
from app.models.session import Session
from app.models.application import Application
from app.models.idle import IdleEvent


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
    def overlap(start1, end1, start2, end2):

        if not start1 or not end1 or not start2 or not end2:
            return 0

        start = max(start1, start2)
        end = min(end1, end2)

        if end <= start:
            return 0

        return int(
            (end - start).total_seconds()
        )

    @staticmethod
    def _effective_working_seconds(
        session,
        session_start,
        session_end,
        overlap_start,
        overlap_end,
    ):
        """
        Working seconds for the slice of a session that falls inside one
        reporting period (day/week/month bucket).

        The agent only reports one monitored-awake duration_seconds for
        the whole session, not a per-day breakdown, so a session that
        spans multiple days can't be split exactly. This applies a
        proportional awake-time approximation: the session's total
        monitored-awake duration is allocated across the days it touches
        in proportion to each day's share of the session's total
        wall-clock time, then clamped to that day's own wall-clock
        overlap so the approximation can never inflate a single day's
        working time beyond what the timestamps allow.

        Falls back to raw wall-clock overlap when duration_seconds is
        unknown (older/unsynced sessions).
        """

        wall_overlap_seconds = int(
            (overlap_end - overlap_start).total_seconds()
        )

        duration_seconds = session.duration_seconds

        if duration_seconds is None:
            return wall_overlap_seconds

        total_session_wall_seconds = int(
            (session_end - session_start).total_seconds()
        )

        if total_session_wall_seconds <= 0:
            return wall_overlap_seconds

        # Protect against a bad/stale duration value before prorating it.
        clamped_duration = max(
            0,
            min(duration_seconds, total_session_wall_seconds),
        )

        share = clamped_duration * (
            wall_overlap_seconds / total_session_wall_seconds
        )

        return max(
            0,
            min(int(round(share)), wall_overlap_seconds),
        )

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
                            "applications": {},
                        }

                    aggregate = user_totals[
                        username
                    ]

                    # ------------------------------------------------
                    # Working time for this reporting period
                    #
                    # A session can span midnight / multiple days.
                    # For a daily report, count only the portion of
                    # the session that falls inside this day.
                    #
                    # Idle periods are removed below, so:
                    #
                    # working = tracked session time
                    # active  = working - idle
                    # ------------------------------------------------
                    working_seconds = (
                        ProductivityReportService._effective_working_seconds(
                            session,
                            session_start,
                            session_end,
                            overlap_start,
                            overlap_end,
                        )
                    )

                    aggregate[
                        "working_seconds"
                    ] += working_seconds

                    idle_events = (
                        db.query(IdleEvent)
                        .filter(
                            IdleEvent.session_id
                            == session.id
                        )
                        .all()
                    )

                    session_idle = 0

                    for idle in idle_events:

                        idle_start = (
                            ProductivityReportService.normalize(
                                idle.idle_start
                            )
                        )

                        idle_end = (
                            ProductivityReportService.normalize(
                                idle.idle_end
                            )
                            if idle.idle_end
                            else now_utc
                        )

                        session_idle += (
                            ProductivityReportService.overlap(
                                overlap_start,
                                overlap_end,
                                idle_start,
                                idle_end,
                            )
                        )

                    session_idle = min(
                        session_idle,
                        working_seconds,
                    )

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

                        elapsed = int(
                            (
                                app_end
                                - app_start
                            ).total_seconds()
                        )

                        # An application cannot have been active longer
                        # than the session's own monitored-awake duration
                        # for this period.
                        elapsed = min(
                            elapsed,
                            working_seconds,
                        )

                        app_idle = 0

                        for idle in idle_events:

                            idle_start = (
                                ProductivityReportService.normalize(
                                    idle.idle_start
                                )
                            )

                            idle_end = (
                                ProductivityReportService.normalize(
                                    idle.idle_end
                                )
                                if idle.idle_end
                                else now_utc
                            )

                            app_idle += (
                                ProductivityReportService.overlap(
                                    app_start,
                                    app_end,
                                    idle_start,
                                    idle_end,
                                )
                            )

                        app_idle = min(
                            app_idle,
                            elapsed,
                        )

                        app_active = max(
                            elapsed - app_idle,
                            0,
                        )

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

                            "productivity_percent":
                                productivity,

                            "applications":
                                application_usage,
                        }
                    )

        return results

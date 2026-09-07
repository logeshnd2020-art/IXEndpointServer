from datetime import date as date_cls, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import require_dashboard_read
from app.models.device import Device
from app.models.session import Session as UserSession
from app.models.installed_application import InstalledApplication
from app.models.device_heartbeat import DeviceHeartbeat
from app.models.application import Application
from app.schemas.device_detail import DeviceMonitorDetailResponse, InstalledApplicationDetail
from app.schemas.timeline import TimelineResponse
from app.schemas.application_timeline import (
    ApplicationDrilldownResponse,
    ApplicationInterval,
    ApplicationUsageDetail,
)
from app.services.timeline_service import TimelineService
from app.services.device_liveness_service import online_status_label
from app.services.agent_evidence_service import attach_reason

# Matches the local-timezone convention already used by ProductivityService
# and ProductivityReportService for interpreting naive DB timestamps and
# reporting-period day boundaries.
LOCAL_TZ = ZoneInfo("Asia/Kolkata")


router = APIRouter()


@router.get("/device/{device_id}")
def device_page(device_id: int):
    # Static shell, same pattern as "/" -- no server-injected data (which
    # previously leaked full device/heartbeat/inventory data with zero
    # auth). All real data is fetched client-side from the /api/device/*
    # endpoints below, which require a valid, role-checked bearer token.
    return FileResponse("templates/device.html")


@router.get(
    "/api/device/{device_id}",
    response_model=DeviceMonitorDetailResponse,
)
def device_detail(
    device_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    device = db.query(Device).filter(Device.id == device_id).first()

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    session = (
        db.query(UserSession)
        .filter(
            UserSession.device_id == device.id,
            UserSession.status == "ACTIVE",
        )
        .first()
    )

    return DeviceMonitorDetailResponse(
        device_id=device.id,
        hostname=device.hostname,
        username=session.username if session else device.username,
        # Phase 3, Item 3 -- computed from last_seen staleness at read
        # time rather than the raw (never-reset) is_online flag.
        # Liveness/visibility only -- see device_liveness_service's
        # module docstring.
        status=online_status_label(device),
        ip_address=device.ip_address,
        last_seen=device.last_seen,
        serial_number=device.serial_number,
        device_uuid=device.device_uuid,
        manufacturer=device.manufacturer,
        model=device.device_model or device.model,
        platform=device.platform,
        os_name=device.os_name,
        os_version=device.os_version or device.macos_version,
        processor=device.processor,
        memory_gb=device.memory_gb,
        storage_gb=device.storage_gb,
        agent_version=device.agent_version,
        is_registered=device.is_registered,
        registration_date=device.registration_date,
    )


@router.get("/api/device/{device_id}/health")
def device_health(
    device_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    heartbeat = (
        db.query(DeviceHeartbeat)
        .filter(DeviceHeartbeat.device_id == device_id)
        .order_by(DeviceHeartbeat.timestamp.desc())
        .first()
    )

    if heartbeat is None:
        raise HTTPException(
            status_code=404,
            detail="No heartbeat data found",
        )

    return {
        "cpu": heartbeat.cpu_usage,
        "memory": heartbeat.memory_usage,
        "disk": heartbeat.disk_usage,
        "battery": heartbeat.battery_level,
        "network": heartbeat.network_name or "-",
        "ip_address": heartbeat.ip_address or "-",
        # Agent-reported hardware MAC address, passed through exactly as
        # received -- None until an agent version actually sends one.
        "mac_address": heartbeat.mac_address,
        "uptime_seconds": heartbeat.uptime_seconds,
        "timestamp": heartbeat.timestamp,
        "logged_in_user": heartbeat.logged_in_user or "-",
    }


@router.get(
    "/api/device/{device_id}/installed-applications",
    response_model=list[InstalledApplicationDetail],
)
def device_installed_applications(
    device_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    applications = (
        db.query(InstalledApplication)
        .filter(
            InstalledApplication.device_id == device_id,
            InstalledApplication.is_installed.is_(True),
        )
        .order_by(InstalledApplication.name.asc())
        .all()
    )

    return [
        InstalledApplicationDetail(
            name=app.name,
            version=app.version,
            bundle_id=app.bundle_id,
            install_path=app.install_path,
            first_seen=app.first_seen,
            last_seen=app.last_seen,
        )
        for app in applications
    ]


def _build_day_timeline(db: Session, device: Device, date_str: str) -> TimelineResponse:
    """
    Builds a contiguous 24h (or up-to-now, for today) timeline for one
    LOCAL calendar day, across every session that overlaps it. Stretches
    of the day with no session open at all are reported as NO_SESSION --
    distinct from SLEEP_CONFIRMED/MONITORING_GAP/OFF_SESSION, all of which
    mean a session was open but not observed (see WorkSessionClassifier
    for how those three are distinguished). Never fills time beyond "now"
    for the current day.
    """
    try:
        day = date_cls.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be in YYYY-MM-DD format")

    day_start_naive = datetime.combine(day, datetime.min.time())
    day_end_naive = day_start_naive + timedelta(days=1)

    day_start_utc = day_start_naive.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    day_end_utc = day_end_naive.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)

    now = datetime.now(timezone.utc)
    effective_end = min(day_end_utc, now)

    segments = []

    if effective_end > day_start_utc:
        sessions = (
            db.query(UserSession)
            .filter(
                UserSession.device_id == device.id,
                UserSession.login_time < day_end_naive,
                or_(
                    UserSession.logout_time.is_(None),
                    UserSession.logout_time >= day_start_naive,
                ),
            )
            .order_by(UserSession.login_time.asc())
            .all()
        )

        cursor = day_start_utc

        for session in sessions:
            session_segments = TimelineService.build(db, session, day_start_utc, effective_end)

            if not session_segments:
                continue

            # 7.8.0 evidence groundwork -- annotate gap-type segments with
            # `reason` from verified agent/server evidence, if any exists.
            # Deliberately done HERE, once per session, rather than inside
            # TimelineService.build() itself: build() is the single
            # canonical interval representation shared by
            # ProductivityService/ProductivityReportService/application
            # attribution as well, none of which need or read `reason` --
            # keeping this lookup out of build() means those call sites
            # pay zero extra query cost, and `type`/duration accounting
            # stays provably untouched everywhere except this one
            # dashboard-facing timeline endpoint.
            session_segments = attach_reason(session_segments, device.id, db)

            seg_start = session_segments[0]["start"]
            seg_end = session_segments[-1]["end"]

            if seg_start > cursor:
                segments.append(
                    {
                        "start": cursor,
                        "end": seg_start,
                        "type": "NO_SESSION",
                        "duration_seconds": int((seg_start - cursor).total_seconds()),
                    }
                )

            segments.extend(session_segments)
            cursor = max(cursor, seg_end)

        if cursor < effective_end:
            segments.append(
                {
                    "start": cursor,
                    "end": effective_end,
                    "type": "NO_SESSION",
                    "duration_seconds": int((effective_end - cursor).total_seconds()),
                }
            )

    return TimelineResponse(
        device_id=device.id,
        hostname=device.hostname,
        date=date_str,
        window_start=day_start_utc,
        window_end=effective_end if effective_end > day_start_utc else day_start_utc,
        segments=segments,
    )


@router.get(
    "/api/device/{device_id}/timeline",
    response_model=TimelineResponse,
)
def device_timeline(
    device_id: int,
    session_id: int = None,
    date: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    device = db.query(Device).filter(Device.id == device_id).first()

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if date is not None:
        return _build_day_timeline(db, device, date)

    if session_id is not None:
        session = (
            db.query(UserSession)
            .filter(
                UserSession.id == session_id,
                UserSession.device_id == device_id,
            )
            .first()
        )
    else:
        # Default to the current ACTIVE session; if none, fall back to the
        # most recently logged-in session so the timeline is never empty
        # purely because the device is currently offline.
        session = (
            db.query(UserSession)
            .filter(
                UserSession.device_id == device_id,
                UserSession.status == "ACTIVE",
            )
            .first()
        )

        if session is None:
            session = (
                db.query(UserSession)
                .filter(UserSession.device_id == device_id)
                .order_by(UserSession.login_time.desc())
                .first()
            )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="No session data available for this device",
        )

    segments = TimelineService.build(db, session)

    window_start = TimelineService._normalize(session.login_time)

    if session.logout_time:
        window_end = TimelineService._normalize(session.logout_time)
    elif segments:
        window_end = segments[-1]["end"]
    else:
        window_end = window_start

    return TimelineResponse(
        device_id=device.id,
        hostname=device.hostname,
        session_id=session.id,
        session_status=session.status,
        window_start=window_start,
        window_end=window_end,
        segments=segments,
    )


def _normalize_application_timestamp(dt):
    """
    applications.start_time/end_time are naive endpoint-local (Asia/Kolkata)
    wall-clock time -- the same convention sessions/idle_events use (see
    TimelineService.CLIENT_LOCAL_TZ) -- not naive UTC. Mirrors
    TimelineService._normalize_local() exactly; duplicated here rather than
    imported since it's a private helper on that class.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_day_application_summary(db: Session, device: Device, date_str: str) -> ApplicationDrilldownResponse:
    """
    Per-application attribution for one LOCAL calendar day, built strictly
    as a downstream layer over the same canonical segments Activity
    Details/Timeline already use for this device/day -- never an
    independent Active/Idle classification. An application record's
    overlap with any segment that is not ACTIVE or IDLE (SLEEP_CONFIRMED,
    MONITORING_GAP, OFF_SESSION, NO_SESSION) contributes nothing: no
    seconds, no interval row. This is what prevents a DarkWake-generated
    application record from ever appearing as Active time, without this
    function ever needing to know what DarkWake is -- it only ever sees
    already-classified segments and reads their type.
    """
    try:
        day = date_cls.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be in YYYY-MM-DD format")

    day_start_naive = datetime.combine(day, datetime.min.time())
    day_end_naive = day_start_naive + timedelta(days=1)

    day_start_utc = day_start_naive.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    day_end_utc = day_end_naive.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)

    now = datetime.now(timezone.utc)
    effective_end = min(day_end_utc, now)

    apps_by_name: dict = {}
    ATTRIBUTABLE_TYPES = ("ACTIVE", "IDLE")

    if effective_end > day_start_utc:
        sessions = (
            db.query(UserSession)
            .filter(
                UserSession.device_id == device.id,
                UserSession.login_time < day_end_naive,
                or_(
                    UserSession.logout_time.is_(None),
                    UserSession.logout_time >= day_start_naive,
                ),
            )
            .order_by(UserSession.login_time.asc())
            .all()
        )

        for session in sessions:
            # Same canonical segments TimelineService/Activity Details
            # already build for this session/day -- not recomputed, not
            # re-classified, just reused.
            session_segments = TimelineService.build(db, session, day_start_utc, effective_end)

            if not session_segments:
                continue

            applications = (
                db.query(Application)
                .filter(
                    Application.device_id == device.id,
                    Application.session_id == session.id,
                )
                .order_by(Application.start_time.asc())
                .all()
            )

            for app in applications:
                app_start = _normalize_application_timestamp(app.start_time)
                app_end = (
                    _normalize_application_timestamp(app.end_time)
                    if app.end_time
                    else now
                )

                if not app_start or app_end <= app_start:
                    continue

                name = app.application_name or "Unknown"

                # One row per canonical ACTIVE/IDLE segment this record
                # overlaps -- never a row for SLEEP_CONFIRMED/
                # MONITORING_GAP/OFF_SESSION/NO_SESSION overlap, which is
                # silently excluded here, exactly like
                # TimelineService.overlap_seconds_by_type()'s existing
                # ACTIVE/IDLE-only totals.
                for seg in session_segments:
                    if seg["type"] not in ATTRIBUTABLE_TYPES:
                        continue

                    ov_start = max(seg["start"], app_start)
                    ov_end = min(seg["end"], app_end)
                    if ov_end <= ov_start:
                        continue

                    bucket = apps_by_name.setdefault(
                        name,
                        {
                            "application": name,
                            "active_seconds": 0,
                            "idle_seconds": 0,
                            "intervals": [],
                        },
                    )

                    duration_seconds = int((ov_end - ov_start).total_seconds())
                    status = seg["type"]  # "ACTIVE" or "IDLE"

                    bucket["intervals"].append(
                        ApplicationInterval(
                            start=ov_start,
                            end=ov_end,
                            status=status,
                            duration_seconds=duration_seconds,
                        )
                    )
                    if status == "ACTIVE":
                        bucket["active_seconds"] += duration_seconds
                    else:
                        bucket["idle_seconds"] += duration_seconds

    applications_out = []
    for bucket in apps_by_name.values():
        bucket["intervals"].sort(key=lambda iv: iv.start)
        applications_out.append(
            ApplicationUsageDetail(
                application=bucket["application"],
                active_seconds=bucket["active_seconds"],
                idle_seconds=bucket["idle_seconds"],
                total_seconds=bucket["active_seconds"] + bucket["idle_seconds"],
                intervals=bucket["intervals"],
            )
        )

    applications_out.sort(key=lambda a: a.active_seconds, reverse=True)

    return ApplicationDrilldownResponse(
        device_id=device.id,
        hostname=device.hostname,
        date=date_str,
        applications=applications_out,
    )


@router.get(
    "/api/device/{device_id}/applications",
    response_model=ApplicationDrilldownResponse,
)
def device_applications(
    device_id: int,
    date: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    device = db.query(Device).filter(Device.id == device_id).first()

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return _build_day_application_summary(db, device, date)

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import require_dashboard_read

from app.models.device import Device
from app.models.session import Session as UserSession
from app.models.application import Application
from app.models.idle import IdleEvent
from app.models.activity import ActivityEvent

from app.schemas.dashboard import DashboardSummaryResponse
from app.schemas.live_device import LiveDeviceResponse
from app.schemas.current_application import CurrentApplicationResponse

from app.schemas.productivity import ProductivityResponse
from app.services.productivity_service import ProductivityService
from app.services.productivity_report_service import ProductivityReportService
from app.services.device_liveness_service import online_status_label

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
)
def summary(
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    return {
        "devices": db.query(Device).count(),
        "active_sessions": db.query(UserSession)
        .filter(UserSession.status == "ACTIVE")
        .count(),
        "applications": db.query(Application).count(),
        "idle_events": db.query(IdleEvent).count(),
        "activity_events": db.query(ActivityEvent).count(),
    }


@router.get(
    "/live-devices",
    response_model=List[LiveDeviceResponse],
)
def live_devices(
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    devices = db.query(Device).all()

    result = []

    for device in devices:

        session = (
            db.query(UserSession)
            .filter(
                UserSession.device_id == device.id,
                UserSession.status == "ACTIVE",
            )
            .first()
        )

        result.append(
            LiveDeviceResponse(
                device_id=device.id,
                hostname=device.hostname,
                serial_number=device.serial_number,
                username=session.username if session else "",
                # Phase 3, Item 3 -- computed from last_seen staleness at
                # read time rather than the raw (never-reset) is_online
                # flag. Liveness/visibility only -- see
                # device_liveness_service's module docstring.
                status=online_status_label(device),
                ip_address=device.ip_address or "",
                last_seen=device.last_seen,
            )
        )

    return result


@router.get(
    "/current-applications",
    response_model=List[CurrentApplicationResponse],
)
def current_applications(
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    devices = db.query(Device).all()

    result = []

    for device in devices:

        session = (
            db.query(UserSession)
            .filter(
                UserSession.device_id == device.id,
                UserSession.status == "ACTIVE",
            )
            .first()
        )

        if not session:
            continue

        # The deployed agent reports application-switch events as
        # already-closed intervals (start_time and end_time both set) in
        # batches, rather than leaving one row open until the next switch.
        # Filtering on end_time IS NULL would therefore almost always find
        # nothing for the live session even though recent, real usage data
        # exists. Instead, take the most recent application by start_time
        # for the active session -- if it happens to still be open
        # (end_time IS NULL) it is genuinely "current"; otherwise it's the
        # last reported usage, and is_currently_open tells the UI which.
        app = (
            db.query(Application)
            .filter(
                Application.device_id == device.id,
                Application.session_id == session.id,
            )
            .order_by(Application.start_time.desc())
            .first()
        )

        if not app:
            continue

        result.append(
            CurrentApplicationResponse(
                hostname=device.hostname,
                username=session.username,
                application=app.application_name,
                window_title=app.window_title or "",
                started_at=app.start_time,
                is_currently_open=app.end_time is None,
            )
        )

    return result
@router.get(
    "/productivity",
    response_model=List[ProductivityResponse],
)
def productivity(
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    return ProductivityService.get_productivity(db)


@router.get(
    "/productivity-report",
)
def productivity_report(
    report_type: str = "daily",
    start_date: str = None,
    end_date: str = None,
    device_id: int = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_dashboard_read),
):
    from datetime import date

    if report_type not in (
        "daily",
        "weekly",
        "monthly",
    ):
        return {
            "error": "report_type must be daily, weekly or monthly"
        }

    parsed_start = (
        date.fromisoformat(start_date)
        if start_date
        else None
    )

    parsed_end = (
        date.fromisoformat(end_date)
        if end_date
        else None
    )

    reports = ProductivityReportService.get_reports(
        db=db,
        report_type=report_type,
        start_date=parsed_start,
        end_date=parsed_end,
        device_id=device_id,
    )

    return {
        "report_type": report_type,
        "reports": reports,
    }

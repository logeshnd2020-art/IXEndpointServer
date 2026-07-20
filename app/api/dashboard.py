from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

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

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
)
def summary(db: Session = Depends(get_db)):
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
def live_devices(db: Session = Depends(get_db)):
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
                hostname=device.hostname,
                serial_number=device.serial_number,
                username=session.username if session else "",
                status="ONLINE" if device.is_online else "OFFLINE",
                ip_address=device.ip_address or "",
                last_seen=device.last_seen,
            )
        )

    return result


@router.get(
    "/current-applications",
    response_model=List[CurrentApplicationResponse],
)
def current_applications(db: Session = Depends(get_db)):
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
            )
        )

    return result
@router.get(
    "/productivity",
    response_model=List[ProductivityResponse],
)
def productivity(db: Session = Depends(get_db)):
    return ProductivityService.get_productivity(db)

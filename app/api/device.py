from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.device import (
    DeviceRegister,
    DeviceResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.services.device_service import DeviceService

router = APIRouter(
    prefix="/api/device",
    tags=["Device"],
)


@router.post(
    "/register",
    response_model=DeviceResponse,
)
def register_device(
    request: DeviceRegister,
    db: Session = Depends(get_db),
):
    device = DeviceService.register(db, request)

    return DeviceResponse(
        device_id=device.id,
        status="registered",
    )


@router.post(
    "/heartbeat",
    response_model=HeartbeatResponse,
)
def heartbeat(
    request: HeartbeatRequest,
    db: Session = Depends(get_db),
):
    device = DeviceService.heartbeat(db, request)

    return HeartbeatResponse(
        status="alive",
        last_seen=device.last_seen.isoformat(),
    )

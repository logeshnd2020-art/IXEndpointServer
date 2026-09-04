from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.database import get_db
from app.schemas.idle import (
    IdleStartRequest,
    IdleEndRequest,
    IdleResponse,
)
from app.services.idle_service import IdleService

router = APIRouter(
    prefix="/api/idle",
    tags=["Idle"],
)


@router.post(
    "/start",
    response_model=IdleResponse,
)
def start(
    request: IdleStartRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):

    idle = IdleService.start(
        db,
        request,
    )

    return IdleResponse(
        idle_id=idle.id,
        idle_start=idle.idle_start,
    )


@router.post("/end")
def end(
    request: IdleEndRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):

    IdleService.end(
        db,
        request,
    )

    return {
        "status": "active"
    }

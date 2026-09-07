from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.database import get_db
from app.core.legacy_endpoint_metrics import record_legacy_hit
from app.schemas.application import (
    ApplicationStartRequest,
    ApplicationStopRequest,
    ApplicationResponse,
)
from app.services.application_service import ApplicationService

router = APIRouter(
    prefix="/api/application",
    tags=["Application"],
)


@router.post(
    "/start",
    response_model=ApplicationResponse,
)
def start(
    request: ApplicationStartRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    record_legacy_hit("POST /api/application/start")

    app = ApplicationService.start(
        db,
        request,
    )

    return ApplicationResponse(
        application_id=app.id,
        application_name=app.application_name,
        start_time=app.start_time,
    )


@router.post("/stop")
def stop(
    request: ApplicationStopRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    record_legacy_hit("POST /api/application/stop")

    ApplicationService.stop(
        db,
        request,
    )

    return {
        "status": "stopped"
    }

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
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
    db: Session = Depends(get_db),
):

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
    db: Session = Depends(get_db),
):

    ApplicationService.stop(
        db,
        request,
    )

    return {
        "status": "stopped"
    }

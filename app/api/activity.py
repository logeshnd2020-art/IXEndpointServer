from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.database import get_db
from app.schemas.activity import (
    ActivityRequest,
    ActivityResponse,
)
from app.services.activity_service import ActivityService

router = APIRouter(
    prefix="/api/activity",
    tags=["Activity"],
)


@router.post(
    "/capture",
    response_model=ActivityResponse,
)
def capture(
    request: ActivityRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):

    activity = ActivityService.create(
        db,
        request,
    )

    return ActivityResponse(
        activity_id=activity.id,
        captured_at=activity.captured_at,
    )

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.database import get_db
from app.schemas.session import (
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    SessionResponse,
)
from app.services.session_service import SessionService

router = APIRouter(
    prefix="/api/session",
    tags=["Session"],
)


@router.post(
    "/login",
    response_model=SessionResponse,
)
def login(
    request: LoginRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    session = SessionService.login(
        db,
        request.serial_number,
        request.username,
    )

    return SessionResponse(
        session_id=session.id,
        status=session.status,
        login_time=session.login_time,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
)
def logout(
    request: LogoutRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    SessionService.logout(
        db,
        request.serial_number,
    )

    return LogoutResponse(
        status="logged_out",
    )

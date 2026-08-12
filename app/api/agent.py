from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.database import get_db
from app.exceptions.device import DeviceAlreadyExists
from app.schemas.agent_session import (
    AgentSessionSyncRequest,
    AgentSessionSyncResponse,
)
from app.schemas.device import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    DeviceInventoryRequest,
    DeviceInventoryResponse,
)
from app.schemas.agent_idle import (
    AgentIdleSyncRequest,
    AgentIdleSyncResponse,
)
from app.services.agent_idle_service import AgentIdleService

from app.schemas.agent_application import (
    AgentApplicationSyncRequest,
    AgentApplicationSyncResponse,
)
from app.schemas.heartbeat import (
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
)
from app.schemas.installed_application import (
    InstalledApplicationsRequest,
    InstalledApplicationsResponse,
)
from app.services.installed_application_service import InstalledApplicationService
from app.services.agent_session_service import AgentSessionService
from app.services.agent_application_service import AgentApplicationService
from app.services.agent_service import AgentService


router = APIRouter(
    prefix="/api/agent",
    tags=["Agent"],
)


@router.post(
    "/register",
    response_model=AgentRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad request"},
        403: {"description": "Invalid or unauthorized enrollment key"},
        409: {"description": "Device conflict or duplicate registration"},
        422: {"description": "Validation error"},
    },
)
def register_agent(
    request: AgentRegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        return AgentService.register_agent(db, request)

    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except DeviceAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Invalid device token or authentication failed"},
        404: {"description": "Device not found"},
        422: {"description": "Validation error"},
    },
)
def heartbeat(
    heartbeat: AgentHeartbeatRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    return AgentService.heartbeat(
        db,
        heartbeat,
        current_device,
    )


@router.post(
    "/inventory",
    response_model=DeviceInventoryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Invalid device token or authentication failed"},
        422: {"description": "Validation error"},
    },
)
def update_inventory(
    inventory: DeviceInventoryRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    device = AgentService.update_inventory(
        db,
        inventory,
        current_device,
    )

    return DeviceInventoryResponse(
        status="success",
        device_id=device.id,
    )


@router.post(
    "/applications",
    response_model=InstalledApplicationsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid inventory request"},
        401: {"description": "Invalid device token or authentication failed"},
        422: {"description": "Validation error"},
    },
)
def applications_inventory(
    request: InstalledApplicationsRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    try:
        return InstalledApplicationService.sync_inventory(
            db=db,
            request=request,
            device=current_device,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/session",
    response_model=AgentSessionSyncResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid session sync request"},
        401: {"description": "Invalid device token or authentication failed"},
        422: {"description": "Validation error"},
    },
)
def sync_session(
    request: AgentSessionSyncRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    try:
        return AgentSessionService.sync(
            db=db,
            request=request,
            device=current_device,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/application",
    response_model=AgentApplicationSyncResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid application sync request"},
        401: {"description": "Invalid device token or authentication failed"},
        422: {"description": "Validation error"},
    },
)
def sync_application(
    request: AgentApplicationSyncRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    try:
        return AgentApplicationService.sync(
            db=db,
            request=request,
            device=current_device,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/idle",
    response_model=AgentIdleSyncResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid idle sync request"},
        401: {"description": "Invalid device token or authentication failed"},
        422: {"description": "Validation error"},
    },
)
def sync_idle(
    request: AgentIdleSyncRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    try:
        return AgentIdleService.sync(
            db=db,
            request=request,
            device=current_device,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.exceptions.device import DeviceAlreadyExists
from app.schemas.device import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    DeviceCreateRequest,
    DeviceUpdateRequest,
    DeviceDetailResponse,
)
from app.services.agent_service import AgentService
from app.services.device_service import DeviceService

router = APIRouter(
    prefix="/api",
    tags=["Device"],
)


@router.post(
    "/devices",
    response_model=DeviceDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_device(
    request: DeviceCreateRequest,
    current_user=Depends(require_roles("SuperAdmin", "Admin", "ITSupport")),
    db: Session = Depends(get_db),
):
    return DeviceService.create_device(db, request)


@router.get(
    "/devices",
    response_model=List[DeviceDetailResponse],
)
def list_devices(
    current_user=Depends(require_roles("SuperAdmin", "Admin", "ITSupport", "Manager", "Auditor")),
    db: Session = Depends(get_db),
):
    return DeviceService.list_devices(db)


@router.get(
    "/devices/{device_id}",
    response_model=DeviceDetailResponse,
)
def get_device(
    device_id: int,
    current_user=Depends(require_roles("SuperAdmin", "Admin", "ITSupport", "Manager", "Auditor")),
    db: Session = Depends(get_db),
):
    return DeviceService.get_device(db, device_id)


@router.put(
    "/devices/{device_id}",
    response_model=DeviceDetailResponse,
)
def update_device(
    device_id: int,
    request: DeviceUpdateRequest,
    current_user=Depends(require_roles("SuperAdmin", "Admin", "ITSupport")),
    db: Session = Depends(get_db),
):
    return DeviceService.update_device(db, device_id, request)


@router.delete(
    "/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_device(
    device_id: int,
    current_user=Depends(require_roles("SuperAdmin", "Admin")),
    db: Session = Depends(get_db),
):
    DeviceService.delete_device(db, device_id)


@router.post(
    "/device/register",
    response_model=AgentRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad request"},
        403: {"description": "Invalid enrollment key"},
        409: {"description": "Device conflict or duplicate registration"},
        422: {"description": "Validation error"},
    },
)
def register_device(
    request: AgentRegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        return AgentService.register_agent(db, request)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DeviceAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

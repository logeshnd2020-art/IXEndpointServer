from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.schemas.enrollment_key import (
    EnrollmentKeyCreateRequest,
    EnrollmentKeyCreateResponse,
    EnrollmentKeyResponse,
)
from app.services.enrollment_key_service import EnrollmentKeyService

router = APIRouter(
    prefix="/api/admin/enrollment-keys",
    tags=["EnrollmentKeys"],
)


@router.post(
    "/",
    response_model=EnrollmentKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create enrollment key",
    description=(
        "Create an enrollment key that expires after a relative number of hours. "
        "The request accepts expires_in_hours and the server computes expires_at. "
        "This prevents clients from setting absolute expiration timestamps directly."
    ),
)
def create_enrollment_key(
    request: EnrollmentKeyCreateRequest,
    current_user=Depends(require_roles("SuperAdmin", "Admin")),
    db: Session = Depends(get_db),
):
    enrollment_key, key = EnrollmentKeyService.generate_enrollment_key(
        db=db,
        name=request.name,
        expires_in_hours=request.expires_in_hours,
        max_devices=request.max_devices,
        created_by=current_user.username,
    )

    return EnrollmentKeyCreateResponse(
        id=key.id,
        name=key.name,
        expires_at=key.expires_at,
        max_devices=key.max_devices,
        devices_registered=key.devices_registered,
        is_active=key.is_active,
        created_by=key.created_by,
        created_at=key.created_at,
        enrollment_key=enrollment_key,
    )


@router.get("/", response_model=list[EnrollmentKeyResponse])
def list_enrollment_keys(
    current_user=Depends(require_roles("SuperAdmin", "Admin")),
    db: Session = Depends(get_db),
):
    keys = EnrollmentKeyService.list_enrollment_keys(db)
    return [EnrollmentKeyResponse.from_orm(key) for key in keys]


@router.get("/{key_id}", response_model=EnrollmentKeyResponse)
def get_enrollment_key(
    key_id: int,
    current_user=Depends(require_roles("SuperAdmin", "Admin")),
    db: Session = Depends(get_db),
):
    key = EnrollmentKeyService.get_enrollment_key(db, key_id)
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment key not found")
    return EnrollmentKeyResponse.from_orm(key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment_key(
    key_id: int,
    current_user=Depends(require_roles("SuperAdmin", "Admin")),
    db: Session = Depends(get_db),
):
    key = EnrollmentKeyService.delete_enrollment_key(db, key_id)
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment key not found")

from typing import Callable

from datetime import datetime, timezone
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, hash_value
from app.models.device import Device
from app.models.user import User
from app.repositories.device_repository import DeviceRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if payload.get("type") != "access" or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or invalid user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_device(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
) -> Device:
    if not authorization or not authorization.startswith("Device "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Device"},
        )

    token = authorization[len("Device ") :].strip()
    token_hash = hash_value(token)

    device = DeviceRepository.get_device_by_token_hash(db, token_hash)

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate device credentials",
            headers={"WWW-Authenticate": "Device"},
        )

    if not device.is_registered:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate device credentials",
            headers={"WWW-Authenticate": "Device"},
        )

    device.token_last_used = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)

    return device


def require_roles(*allowed_roles: str) -> Callable:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.role or current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user

    return role_checker


# Roles allowed to view the read-only monitoring dashboard (device list,
# device detail, productivity, application usage, etc). MONITOR is
# deliberately included here only -- it is never added to any
# create/update/delete allowlist (see app/api/device.py,
# app/api/enrollment_key.py), so it stays read-only by simple omission.
DASHBOARD_READ_ROLES = (
    "SuperAdmin",
    "Admin",
    "ITSupport",
    "Manager",
    "Auditor",
    "MONITOR",
)


require_dashboard_read = require_roles(*DASHBOARD_READ_ROLES)

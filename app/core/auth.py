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
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
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
    print('==========================')
    print('HEARTBEAT AUTH DEBUG')
    print('==========================')
    print('Raw Authorization header:', authorization)

    if not authorization or not authorization.startswith("Device "):
        print('failure: invalid scheme')
        print('CONCLUSION: Token hash mismatch')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Device"},
        )

    token = authorization[len("Device ") :].strip()
    print('Extracted token:', token)

    token_hash = hash_value(token)
    print('SHA256 hash generated from token:', token_hash)

    query = db.query(Device).filter(Device.device_token_hash == token_hash)
    try:
        compiled_query = str(query.statement.compile(dialect=db.bind.dialect, compile_kwargs={"literal_binds": True}))
    except Exception:
        compiled_query = str(query)
    print('SQLAlchemy query being executed:', compiled_query)

    device = DeviceRepository.get_device_by_token_hash(db, token_hash)
    print('DeviceRepository.get_device_by_token_hash() result:', device)

    if device is None:
        total_devices = db.query(Device).count()
        hashes = [row[0] for row in db.query(Device.device_token_hash).limit(10).all()]
        print('Count of devices in database:', total_devices)
        print('First 10 chars of every device_token_hash (limited to 10 rows):')
        for token_hash_value in hashes:
            print('  ', (token_hash_value or '')[:10])
        print('First 10 chars of computed token_hash:', token_hash[:10])
        print('CONCLUSION: Token hash mismatch')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate device credentials",
            headers={"WWW-Authenticate": "Device"},
        )

    print('Returned device id:', device.id)
    print('Returned device hostname:', device.hostname)
    print('Returned device is_registered:', device.is_registered)
    print('Returned device status:', device.status)

    if not device.is_registered:
        print('CONCLUSION: Registration stored wrong hash')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate device credentials",
            headers={"WWW-Authenticate": "Device"},
        )

    device.token_last_used = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)

    print('CONCLUSION: Authentication successful')
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

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import LoginRequest, AuthResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    result = AuthService.authenticate(db, request.username_or_email, request.password)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return result


@router.post("/token", response_model=AuthResponse)
def token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    result = AuthService.authenticate(db, form_data.username, form_data.password)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return result

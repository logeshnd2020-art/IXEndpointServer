from fastapi import APIRouter, Depends, HTTPException
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

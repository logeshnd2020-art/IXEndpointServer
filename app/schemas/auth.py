from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class AuthUser(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr]
    is_active: bool


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: AuthUser

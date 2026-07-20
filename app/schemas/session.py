from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    serial_number: str
    username: str


class LogoutRequest(BaseModel):
    serial_number: str


class SessionResponse(BaseModel):
    session_id: int
    status: str
    login_time: datetime


class LogoutResponse(BaseModel):
    status: str

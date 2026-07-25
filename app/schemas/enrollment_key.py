from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnrollmentKeyCreateRequest(BaseModel):
    name: str
    expires_in_hours: int
    max_devices: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "temporary-enroll-key",
                "expires_in_hours": 24,
                "max_devices": 10,
            }
        }
    )


class EnrollmentKeyResponse(BaseModel):
    id: int
    name: str
    expires_at: datetime
    max_devices: int
    devices_registered: int
    is_active: bool
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EnrollmentKeyCreateResponse(EnrollmentKeyResponse):
    enrollment_key: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "temporary-enroll-key",
                "expires_at": "2026-07-23T12:00:00Z",
                "max_devices": 10,
                "devices_registered": 0,
                "is_active": True,
                "created_by": "admin",
                "created_at": "2026-07-22T12:00:00Z",
                "enrollment_key": "XyZ123abc...",
            }
        }
    )

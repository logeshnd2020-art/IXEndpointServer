from typing import List, Optional

from pydantic import BaseModel, Field


class InstalledApplicationItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: Optional[str] = None
    bundle: Optional[str] = None
    path: Optional[str] = None


class InstalledApplicationsRequest(BaseModel):
    serial: str
    applications: List[InstalledApplicationItem]


class InstalledApplicationsResponse(BaseModel):
    status: str
    received: int
    created: int
    updated: int
    removed: int

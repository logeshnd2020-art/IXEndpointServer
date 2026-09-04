from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.role import RoleResponse
from app.services.role_service import RoleService

router = APIRouter(prefix="/api/roles", tags=["Roles"])


@router.get("/", response_model=list[RoleResponse])
def list_roles(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return RoleService.list_roles(db)

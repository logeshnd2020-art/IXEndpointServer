from typing import List

from sqlalchemy.orm import Session

from app.repositories.role_repository import RoleRepository
from app.schemas.role import RoleResponse


class RoleService:
    @staticmethod
    def list_roles(db: Session) -> List[RoleResponse]:
        roles = RoleRepository.get_all_roles(db)
        return [RoleResponse.from_orm(role) for role in roles]

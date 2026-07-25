from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.role import Role


class RoleRepository:
    @staticmethod
    def get_role_by_name(db: Session, name: str) -> Optional[Role]:
        return db.query(Role).filter(Role.name == name).first()

    @staticmethod
    def get_all_roles(db: Session) -> List[Role]:
        return db.query(Role).order_by(Role.id).all()

    @staticmethod
    def create_role(db: Session, name: str, description: str = None) -> Role:
        role = Role(name=name, description=description)
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

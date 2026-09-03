#!/usr/bin/env python3
"""Seed default RBAC roles into the database."""
from typing import List

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.repositories.role_repository import RoleRepository


DEFAULT_ROLES: List[dict] = [
    {"name": "SuperAdmin", "description": "Full access to all system features."},
    {"name": "Admin", "description": "Administrative access to manage system settings."},
    {"name": "ITSupport", "description": "Technical support role for system maintenance."},
    {"name": "Manager", "description": "Managerial role with team oversight permissions."},
    {"name": "Employee", "description": "Standard employee role with limited access."},
    {"name": "Auditor", "description": "Read-only access for auditing and reporting."},
    {"name": "MONITOR", "description": "Read-only dashboard access for endpoint monitoring."},
]


def main() -> None:
    db: Session = SessionLocal()
    try:
        for role_data in DEFAULT_ROLES:
            existing = RoleRepository.get_role_by_name(db, role_data["name"])
            if existing:
                print(f"Role already exists: {existing.name}")
                continue

            role = RoleRepository.create_role(
                db,
                name=role_data["name"],
                description=role_data["description"],
            )
            print(f"Created role: {role.name} ({role.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()

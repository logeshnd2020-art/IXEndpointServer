#!/usr/bin/env python3
"""One-time script to create the dedicated read-only MONITOR dashboard
account.

Idempotent: safe to run multiple times. Requires scripts/seed_roles.py to
have been run first so the MONITOR role exists.

The plaintext password is only ever used locally to compute a bcrypt hash
via app.core.security.get_password_hash -- it is never written to the
database, logged, or stored anywhere in plaintext.
"""
from sqlalchemy import or_

from app.core.database import SessionLocal
from app.models.user import User
from app.core import security
from app.repositories.role_repository import RoleRepository


def main() -> None:
    username = "monitor"
    email = "monitor@intellectyx.com"
    password = "REDACTED-ROTATED-CREDENTIAL"
    role_name = "MONITOR"

    db = SessionLocal()
    try:
        role = RoleRepository.get_role_by_name(db, role_name)

        if role is None:
            print(
                f"Role '{role_name}' does not exist yet. "
                "Run scripts/seed_roles.py first."
            )
            return

        existing = (
            db.query(User)
            .filter(or_(User.username == username, User.email == email))
            .first()
        )

        if existing:
            # Idempotent: make sure the role assignment is correct even if
            # the user already existed, but never touch/echo the password.
            if existing.role_id != role.id:
                existing.role_id = role.id
                db.commit()
                db.refresh(existing)
                print(
                    f"Updated existing user id={existing.id} "
                    f"username={existing.username} to role={role_name}"
                )
            else:
                print(
                    f"User already exists with correct role: "
                    f"id={existing.id}, username={existing.username}, role={role_name}"
                )
            return

        password_hash = security.get_password_hash(password)

        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            is_active=True,
            role_id=role.id,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(
            f"Created user: id={user.id}, username={user.username}, "
            f"email={user.email}, role={role_name}"
        )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

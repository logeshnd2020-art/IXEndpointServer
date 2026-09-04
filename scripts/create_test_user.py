#!/usr/bin/env python3
"""One-time dev script to create a test admin user.

Idempotent: safe to run multiple times.

The plaintext password is only ever used locally to compute a bcrypt hash
via app.core.security.get_password_hash -- it is never written to the
database, logged, or stored anywhere in plaintext. It must be supplied via
the TEST_ADMIN_USER_PASSWORD environment variable (same convention as
MONITOR_USER_PASSWORD in scripts/create_monitor_user.py) rather than
hardcoded here, so no real credential ever lives in source control.
"""
import os
import sys

from sqlalchemy import or_

from app.core.database import SessionLocal
from app.models.user import User
from app.core import security


def main() -> None:
    username = "admin"
    email = "admin@example.com"
    password = os.environ.get("TEST_ADMIN_USER_PASSWORD")
    role = "Admin"

    if not password:
        print(
            "TEST_ADMIN_USER_PASSWORD environment variable is not set -- "
            "refusing to create/update the test admin account without an "
            "explicit password. Set it and re-run."
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = (
            db.query(User)
            .filter(or_(User.username == username, User.email == email))
            .first()
        )

        if existing:
            print(f"User already exists: id={existing.id}, username={existing.username}, email={existing.email}")
            return

        password_hash = security.get_password_hash(password)

        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Note: the `User` model does not have a `role` column by default in this
        # project. We print the intended role for developer convenience.
        print(f"Created user: id={user.id}, username={user.username}, email={user.email}, role={role}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

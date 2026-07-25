from datetime import timedelta
from typing import Dict, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.core import security


class AuthService:
    """Authentication service responsible for validating credentials
    and issuing tokens. This implementation queries the `User` model
    directly and intentionally keeps logic here so it can be refactored
    later to call a repository.
    """

    @staticmethod
    def authenticate(db: Session, username_or_email: str, password: str) -> Optional[Dict]:
        """Authenticate a user by `username_or_email` and `password`.

        Returns a dict with tokens and basic user info on success, or
        `None` when authentication fails.
        """
        user = (
            db.query(User)
            .filter(or_(User.username == username_or_email, User.email == username_or_email))
            .first()
        )

        if not user:
            return None

        if not user.is_active:
            return None

        if not security.verify_password(password, user.password_hash):
            return None

        access_token = security.create_access_token(subject=user.id)
        refresh_token = security.create_refresh_token(subject=user.id)

        response = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(security.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
            },
        }

        return response

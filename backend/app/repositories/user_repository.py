"""
Database access for users.

Nothing outside this module writes user SQL, and nothing inside it knows about
passwords, permissions or HTTP. Hashing in particular stays out: the repository
stores whatever hash it is handed, and `app/services/user_service.py` decides
what that hash should be.
"""

import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from app.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- queries ---

    def get(self, user_id: uuid.UUID) -> User | None:
        """The user with this id, or None."""
        return self.session.get(User, user_id)

    def find_by_email(self, email: str) -> User | None:
        """The user registered with this email, or None."""
        return self.session.exec(select(User).where(User.email == email)).first()

    def list(self, *, skip: int = 0, limit: int = 100) -> Sequence[User]:
        """Users, newest first."""
        statement = (
            select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
        )
        return self.session.exec(statement).all()

    def count(self) -> int:
        """How many users exist."""
        return self.session.exec(select(func.count()).select_from(User)).one()

    # --- persistence ---

    def save(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def delete(self, user: User) -> None:
        """Remove the user; boxes they own are kept, and their claim released."""
        self.session.delete(user)
        self.session.commit()

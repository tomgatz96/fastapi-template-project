"""
Account rules.

Who may look at whom, when an email counts as taken, what happens when someone
changes their own password. Passwords are hashed here rather than in the
repository, because how a secret is protected is a decision, not a detail of
storage.

The status codes these rules used to raise directly are preserved exactly, via
the domain exceptions in `app/services/exceptions.py`.
"""

import uuid

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    UpdatePassword,
    User,
    UserCreate,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.repositories.user_repository import UserRepository
from app.services.exceptions import (
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
)
from app.utils import generate_new_account_email, send_email

SELF_DELETE_DENIED = "Super users are not allowed to delete themselves"


def new_user(user_create: UserCreate) -> User:
    """A User with its password hashed, ready to be stored."""
    return User.model_validate(
        user_create,
        update={"hashed_password": get_password_hash(user_create.password)},
    )


def apply_update(user: User, user_in: UserUpdate) -> User:
    """
    Copy the supplied fields onto the user, hashing a new password if one
    was given. Mutates the user but does not save it.
    """
    fields = user_in.model_dump(exclude_unset=True)
    extra: dict[str, str] = {}
    password = fields.pop("password", None)
    if password is not None:
        extra["hashed_password"] = get_password_hash(password)
    user.sqlmodel_update(fields, update=extra)
    return user


class UserService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    # --- queries ---

    def list_users(self, *, skip: int = 0, limit: int = 100) -> UsersPublic:
        return UsersPublic(
            data=list(self.users.list(skip=skip, limit=limit)),
            count=self.users.count(),
        )

    def get_user(self, user_id: uuid.UUID, current_user: User) -> User:
        """
        Anyone may look at their own account; only superusers may look at
        anyone else's.

        The privilege check comes before the existence check on purpose, so
        that a stranger cannot use 404s to find out which accounts exist.
        """
        user = self.users.get(user_id)
        if user is not None and user.id == current_user.id:
            return user
        if not current_user.is_superuser:
            raise PermissionDeniedError("The user doesn't have enough privileges")
        if user is None:
            raise NotFoundError("User not found")
        return user

    # --- commands ---

    def create_user(self, user_in: UserCreate) -> User:
        """Create an account on someone's behalf, and tell them about it."""
        if self.users.find_by_email(user_in.email) is not None:
            raise InvalidRequestError(
                "The user with this email already exists in the system."
            )

        user = self.users.save(new_user(user_in))

        if settings.emails_enabled and user_in.email:
            email_data = generate_new_account_email(
                email_to=user_in.email,
                username=user_in.email,
                password=user_in.password,
            )
            send_email(
                email_to=user_in.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        return user

    def register(self, user_in: UserRegister) -> User:
        """Sign yourself up. No email is sent: you already know the password."""
        if self.users.find_by_email(user_in.email) is not None:
            raise InvalidRequestError(
                "The user with this email already exists in the system"
            )
        return self.users.save(new_user(UserCreate.model_validate(user_in)))

    def update_user(self, user_id: uuid.UUID, user_in: UserUpdate) -> User:
        """Change someone else's account. Superuser only, enforced at the route."""
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("The user with this id does not exist in the system")
        if user_in.email:
            self._require_email_free(user_in.email, owner_id=user_id)
        return self.users.save(apply_update(user, user_in))

    def update_profile(self, current_user: User, user_in: UserUpdateMe) -> User:
        """Change your own name or email."""
        if user_in.email:
            self._require_email_free(user_in.email, owner_id=current_user.id)
        current_user.sqlmodel_update(user_in.model_dump(exclude_unset=True))
        return self.users.save(current_user)

    def change_password(self, current_user: User, body: UpdatePassword) -> None:
        """Change your own password, proving you know the current one."""
        verified, _ = verify_password(
            body.current_password, current_user.hashed_password
        )
        if not verified:
            raise InvalidRequestError("Incorrect password")
        if body.current_password == body.new_password:
            raise InvalidRequestError(
                "New password cannot be the same as the current one"
            )
        current_user.hashed_password = get_password_hash(body.new_password)
        self.users.save(current_user)

    def delete_user(self, user_id: uuid.UUID, current_user: User) -> None:
        """Delete someone else's account. Superuser only, enforced at the route."""
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if user.id == current_user.id:
            raise PermissionDeniedError(SELF_DELETE_DENIED)
        self.users.delete(user)

    def delete_own_account(self, current_user: User) -> None:
        """
        Close your own account.

        Superusers are refused so that the last administrator cannot lock
        everyone out of the system.
        """
        if current_user.is_superuser:
            raise PermissionDeniedError(SELF_DELETE_DENIED)
        self.users.delete(current_user)

    # --- internals ---

    def _require_email_free(self, email: str, *, owner_id: uuid.UUID) -> None:
        """No two accounts may share an email, but keeping your own is fine."""
        existing = self.users.find_by_email(email)
        if existing is not None and existing.id != owner_id:
            raise ConflictError("User with this email already exists")

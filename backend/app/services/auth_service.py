"""
Signing in and password recovery.

Deliberately tight-lipped: a wrong password and an unknown email produce the
same answer, and asking for a recovery link tells you nothing about whether
the address is registered. That is a security rule, not a UI preference, which
is why it lives here rather than in the controller.
"""

from datetime import timedelta

from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import Token, User
from app.repositories.user_repository import UserRepository
from app.services.exceptions import InvalidRequestError, NotFoundError
from app.utils import (
    EmailData,
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

# Verifying against a throwaway hash when no user matches keeps the response
# time the same whether or not the email is registered, so timing cannot be
# used to enumerate accounts.
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"

INVALID_CREDENTIALS = "Incorrect email or password"
INACTIVE_USER = "Inactive user"
INVALID_TOKEN = "Invalid token"


class AuthService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    # --- signing in ---

    def authenticate(self, email: str, password: str) -> User | None:
        """
        The user with these credentials, or None.

        Rehashes the stored password when the hashing parameters have moved
        on, so accounts strengthen quietly as people sign in.
        """
        user = self.users.find_by_email(email)
        if user is None:
            verify_password(password, DUMMY_HASH)
            return None

        verified, updated_hash = verify_password(password, user.hashed_password)
        if not verified:
            return None

        if updated_hash:
            user.hashed_password = updated_hash
            self.users.save(user)
        return user

    def login(self, email: str, password: str) -> Token:
        """Exchange credentials for an access token."""
        user = self.authenticate(email, password)
        if user is None:
            raise InvalidRequestError(INVALID_CREDENTIALS)
        if not user.is_active:
            raise InvalidRequestError(INACTIVE_USER)

        expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return Token(
            access_token=security.create_access_token(user.id, expires_delta=expires)
        )

    # --- password recovery ---

    def send_recovery_email(self, email: str) -> None:
        """
        Email a reset link, if the address belongs to someone.

        Silent when it does not: the caller returns the same message either
        way, so that this endpoint cannot be used to discover who has an
        account.
        """
        user = self.users.find_by_email(email)
        if user is None:
            return

        email_data = self._reset_email(user.email)
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )

    def reset_password(self, token: str, new_password: str) -> None:
        """
        Set a new password from a reset link.

        An expired link and an unknown account give the same error, again so
        that nothing is revealed about who is registered.
        """
        email = verify_password_reset_token(token=token)
        if not email:
            raise InvalidRequestError(INVALID_TOKEN)

        user = self.users.find_by_email(email)
        if user is None:
            raise InvalidRequestError(INVALID_TOKEN)
        if not user.is_active:
            raise InvalidRequestError(INACTIVE_USER)

        user.hashed_password = get_password_hash(new_password)
        self.users.save(user)

    def recovery_email_preview(self, email: str) -> EmailData:
        """
        The recovery email as it would be sent, for superusers checking the
        template. This one does say when an address is unknown, because only
        an administrator can reach it.
        """
        user = self.users.find_by_email(email)
        if user is None:
            raise NotFoundError(
                "The user with this username does not exist in the system."
            )
        return self._reset_email(user.email)

    # --- internals ---

    @staticmethod
    def _reset_email(email: str) -> EmailData:
        token = generate_password_reset_token(email=email)
        return generate_reset_password_email(email_to=email, email=email, token=token)

"""
Unit tests for signing in and password recovery.

The point of most of these is what the service refuses to reveal: a wrong
password and an unknown address must be indistinguishable to a caller, and
asking for a recovery link must say nothing about who is registered.
"""

import uuid

import pytest

from app.core.security import verify_password
from app.models import User, UserCreate
from app.services.auth_service import INACTIVE_USER, INVALID_TOKEN, AuthService
from app.services.exceptions import InvalidRequestError, NotFoundError
from app.services.user_service import new_user
from app.utils import generate_password_reset_token
from tests.services.test_user_service import FakeUserRepository


def make_user(
    email: str | None = None, *, password: str = "secret123", active: bool = True
) -> User:
    user = new_user(
        UserCreate(email=email or f"{uuid.uuid4()}@example.com", password=password)
    )
    user.is_active = active
    return user


def service_with(*users: User) -> tuple[AuthService, FakeUserRepository]:
    repo = FakeUserRepository(*users)
    return AuthService(repo), repo


# --- authenticating ---


def test_correct_credentials_return_the_user() -> None:
    user = make_user("me@example.com", password="right-password")
    service, _ = service_with(user)
    assert service.authenticate("me@example.com", "right-password") is user


def test_a_wrong_password_returns_nothing() -> None:
    user = make_user("me@example.com", password="right-password")
    service, _ = service_with(user)
    assert service.authenticate("me@example.com", "wrong-password") is None


def test_an_unknown_email_returns_nothing() -> None:
    service, _ = service_with()
    assert service.authenticate("nobody@example.com", "any-password") is None


# --- logging in ---


def test_login_issues_a_token() -> None:
    user = make_user("me@example.com", password="right-password")
    service, _ = service_with(user)
    token = service.login("me@example.com", "right-password")
    assert token.access_token
    assert token.token_type == "bearer"


def test_a_wrong_password_and_an_unknown_email_give_the_same_error() -> None:
    """Otherwise the error message would reveal which addresses exist."""
    user = make_user("me@example.com", password="right-password")
    service, _ = service_with(user)

    with pytest.raises(InvalidRequestError) as wrong_password:
        service.login("me@example.com", "wrong-password")
    with pytest.raises(InvalidRequestError) as unknown_email:
        service.login("nobody@example.com", "wrong-password")

    assert wrong_password.value.detail == unknown_email.value.detail


def test_a_deactivated_user_cannot_log_in() -> None:
    user = make_user("me@example.com", password="right-password", active=False)
    service, _ = service_with(user)

    with pytest.raises(InvalidRequestError) as error:
        service.login("me@example.com", "right-password")
    assert error.value.detail == INACTIVE_USER


# --- password recovery ---


def test_recovery_for_an_unknown_address_is_silent() -> None:
    """No user, no email, no error: the caller cannot tell either way."""
    service, _ = service_with()
    assert service.send_recovery_email("nobody@example.com") is None


def test_resetting_with_a_bad_token_is_refused() -> None:
    service, _ = service_with()
    with pytest.raises(InvalidRequestError) as error:
        service.reset_password("not-a-real-token", "new-password")
    assert error.value.detail == INVALID_TOKEN


def test_a_valid_token_for_a_deleted_user_looks_like_a_bad_token() -> None:
    service, _ = service_with()
    token = generate_password_reset_token(email="gone@example.com")

    with pytest.raises(InvalidRequestError) as error:
        service.reset_password(token, "new-password")
    assert error.value.detail == INVALID_TOKEN


def test_a_valid_reset_changes_the_stored_password() -> None:
    user = make_user("me@example.com", password="old-password")
    service, repo = service_with(user)
    token = generate_password_reset_token(email="me@example.com")

    service.reset_password(token, "new-password")

    verified, _ = verify_password("new-password", repo.users[user.id].hashed_password)
    assert verified


def test_a_deactivated_user_cannot_reset_their_password() -> None:
    user = make_user("me@example.com", active=False)
    service, _ = service_with(user)
    token = generate_password_reset_token(email="me@example.com")

    with pytest.raises(InvalidRequestError) as error:
        service.reset_password(token, "new-password")
    assert error.value.detail == INACTIVE_USER


def test_the_superuser_preview_does_report_an_unknown_address() -> None:
    """Only administrators can reach it, so there is nothing to protect."""
    service, _ = service_with()
    with pytest.raises(NotFoundError):
        service.recovery_email_preview("nobody@example.com")

"""
Unit tests for the account rules, using an in-memory repository.

These check the decisions — who may see whom, when an email counts as taken,
who is refused deletion — without a database. The rules that need real SQL,
such as the unique constraint on email, stay covered by the API tests.
"""

import uuid

import pytest

from app.models import (
    UpdatePassword,
    User,
    UserCreate,
    UserRegister,
    UserUpdate,
    UserUpdateMe,
)
from app.services.exceptions import (
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
)
from app.services.user_service import UserService, apply_update, new_user


class FakeUserRepository:
    """An in-memory stand-in with the same surface the service uses."""

    def __init__(self, *users: User) -> None:
        self.users = {u.id: u for u in users}
        self.deleted: list[User] = []

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    def find_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    def list(self, *, skip: int = 0, limit: int = 100) -> list[User]:
        return list(self.users.values())[skip : skip + limit]

    def count(self) -> int:
        return len(self.users)

    def save(self, user: User) -> User:
        self.users[user.id] = user
        return user

    def delete(self, user: User) -> None:
        self.users.pop(user.id, None)
        self.deleted.append(user)


def make_user(
    email: str | None = None, *, superuser: bool = False, password: str = "secret123"
) -> User:
    return new_user(
        UserCreate(
            email=email or f"{uuid.uuid4()}@example.com",
            password=password,
            is_superuser=superuser,
        )
    )


def service_with(*users: User) -> tuple[UserService, FakeUserRepository]:
    repo = FakeUserRepository(*users)
    return UserService(repo), repo


# --- hashing helpers ---


def test_new_user_hashes_the_password() -> None:
    user = make_user(password="plaintext")
    assert user.hashed_password != "plaintext"
    assert user.hashed_password.startswith("$argon2")


def test_apply_update_rehashes_a_new_password() -> None:
    user = make_user(password="old-password")
    before = user.hashed_password

    apply_update(user, UserUpdate(password="new-password"))

    assert user.hashed_password != before
    assert user.hashed_password.startswith("$argon2")


def test_apply_update_leaves_the_hash_alone_when_no_password_given() -> None:
    user = make_user()
    before = user.hashed_password

    apply_update(user, UserUpdate(full_name="Renamed"))

    assert user.hashed_password == before
    assert user.full_name == "Renamed"


def test_apply_update_does_not_leave_a_stray_password_attribute() -> None:
    """The plaintext must not survive on the object once it is hashed."""
    user = make_user()
    apply_update(user, UserUpdate(password="new-password"))
    assert getattr(user, "password", None) is None


# --- looking users up ---


def test_anyone_may_read_their_own_account() -> None:
    user = make_user()
    service, _ = service_with(user)
    assert service.get_user(user.id, user).id == user.id


def test_a_normal_user_may_not_read_someone_else() -> None:
    me, other = make_user(), make_user()
    service, _ = service_with(me, other)
    with pytest.raises(PermissionDeniedError):
        service.get_user(other.id, me)


def test_a_superuser_may_read_anyone() -> None:
    admin, other = make_user(superuser=True), make_user()
    service, _ = service_with(admin, other)
    assert service.get_user(other.id, admin).id == other.id


def test_a_missing_user_is_a_403_for_strangers_not_a_404() -> None:
    """Otherwise 404s could be used to discover which accounts exist."""
    me = make_user()
    service, _ = service_with(me)
    with pytest.raises(PermissionDeniedError):
        service.get_user(uuid.uuid4(), me)


def test_a_missing_user_is_a_404_for_superusers() -> None:
    admin = make_user(superuser=True)
    service, _ = service_with(admin)
    with pytest.raises(NotFoundError):
        service.get_user(uuid.uuid4(), admin)


# --- creating accounts ---


def test_create_user_rejects_a_duplicate_email() -> None:
    existing = make_user("taken@example.com")
    service, _ = service_with(existing)
    with pytest.raises(InvalidRequestError):
        service.create_user(UserCreate(email="taken@example.com", password="secret123"))


def test_register_rejects_a_duplicate_email() -> None:
    existing = make_user("taken@example.com")
    service, _ = service_with(existing)
    with pytest.raises(InvalidRequestError):
        service.register(
            UserRegister(email="taken@example.com", password="secret123")
        )


def test_register_stores_the_password_hashed() -> None:
    service, repo = service_with()
    user = service.register(
        UserRegister(email="new@example.com", password="secret123")
    )
    assert repo.users[user.id].hashed_password.startswith("$argon2")


# --- changing accounts ---


def test_updating_to_a_taken_email_conflicts() -> None:
    me, other = make_user("me@example.com"), make_user("other@example.com")
    service, _ = service_with(me, other)
    with pytest.raises(ConflictError):
        service.update_profile(me, UserUpdateMe(email="other@example.com"))


def test_keeping_your_own_email_is_not_a_conflict() -> None:
    me = make_user("me@example.com")
    service, _ = service_with(me)
    updated = service.update_profile(
        me, UserUpdateMe(email="me@example.com", full_name="Me")
    )
    assert updated.full_name == "Me"


def test_updating_a_missing_user_is_not_found() -> None:
    service, _ = service_with()
    with pytest.raises(NotFoundError):
        service.update_user(uuid.uuid4(), UserUpdate(full_name="Ghost"))


def test_changing_password_requires_the_current_one() -> None:
    user = make_user(password="right-password")
    service, _ = service_with(user)
    with pytest.raises(InvalidRequestError):
        service.change_password(
            user,
            UpdatePassword(
                current_password="wrong-password", new_password="new-password"
            ),
        )


def test_the_new_password_must_differ_from_the_old() -> None:
    user = make_user(password="same-password")
    service, _ = service_with(user)
    with pytest.raises(InvalidRequestError):
        service.change_password(
            user,
            UpdatePassword(
                current_password="same-password", new_password="same-password"
            ),
        )


def test_a_valid_password_change_is_stored_hashed() -> None:
    user = make_user(password="old-password")
    service, repo = service_with(user)
    before = user.hashed_password

    service.change_password(
        user,
        UpdatePassword(current_password="old-password", new_password="new-password"),
    )

    assert repo.users[user.id].hashed_password != before


# --- deleting accounts ---


def test_a_superuser_may_not_delete_themselves() -> None:
    admin = make_user(superuser=True)
    service, _ = service_with(admin)
    with pytest.raises(PermissionDeniedError):
        service.delete_own_account(admin)


def test_a_normal_user_may_close_their_own_account() -> None:
    user = make_user()
    service, repo = service_with(user)
    service.delete_own_account(user)
    assert repo.deleted == [user]


def test_a_superuser_may_not_delete_themselves_by_id_either() -> None:
    admin = make_user(superuser=True)
    service, _ = service_with(admin)
    with pytest.raises(PermissionDeniedError):
        service.delete_user(admin.id, admin)


def test_deleting_a_missing_user_is_not_found() -> None:
    admin = make_user(superuser=True)
    service, _ = service_with(admin)
    with pytest.raises(NotFoundError):
        service.delete_user(uuid.uuid4(), admin)

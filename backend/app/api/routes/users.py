"""
HTTP endpoints for users.

Controllers stay thin: bind the route, take the authenticated user, call one
service method. Account rules live in `app/services/user_service.py`, and
broken rules become status codes in `app/api/errors.py`.

Superuser-only endpoints keep their `get_current_active_superuser` dependency
rather than checking inside the service, so the requirement is visible in the
generated API docs.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, UserServiceDep, get_current_active_superuser
from app.models import (
    Message,
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(service: UserServiceDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    return service.list_users(skip=skip, limit=limit)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, service: UserServiceDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    return service.create_user(user_in)


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, service: UserServiceDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """
    return service.update_profile(current_user, user_in)


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, service: UserServiceDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    service.change_password(current_user, body)
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(service: UserServiceDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    service.delete_own_account(current_user)
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(service: UserServiceDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    return service.register(user_in)


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, service: UserServiceDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    return service.get_user(user_id, current_user)


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    service: UserServiceDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """
    return service.update_user(user_id, user_in)


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    service: UserServiceDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    service.delete_user(user_id, current_user)
    return Message(message="User deleted successfully")

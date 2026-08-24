from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import User, UserCreate, UserUpdate
from app.repositories.user_repository import UserRepository
from app.services.user_service import apply_update, new_user
from tests.utils.utils import random_email, random_lower_string


def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    data = {"username": email, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_user(db: Session, user_in: UserCreate) -> User:
    """Store a user with its password hashed, bypassing the service rules."""
    return UserRepository(db).save(new_user(user_in))


def create_random_user(db: Session) -> User:
    email = random_email()
    password = random_lower_string()
    return create_user(db, UserCreate(email=email, password=password))


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session
) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    users = UserRepository(db)
    user = users.find_by_email(email)
    if not user:
        create_user(db, UserCreate(email=email, password=password))
    else:
        if not user.id:
            raise Exception("User id not set")
        users.save(apply_update(user, UserUpdate(password=password)))

    return user_authentication_headers(client=client, email=email, password=password)

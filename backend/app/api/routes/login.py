"""
HTTP endpoints for signing in and password recovery.

The controllers here are thin by design: what a wrong password reveals, and
what a recovery request reveals, are security decisions that live in
`app/services/auth_service.py` where they can be read in one place.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, CurrentUser, get_current_active_superuser
from app.models import Message, NewPassword, Token, UserPublic

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    service: AuthServiceDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    return service.login(form_data.username, form_data.password)


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(email: str, service: AuthServiceDep) -> Message:
    """
    Password Recovery
    """
    service.send_recovery_email(email)
    # The same response either way, so this endpoint cannot be used to work
    # out which addresses are registered.
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(service: AuthServiceDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    service.reset_password(body.token, body.new_password)
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, service: AuthServiceDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    email_data = service.recovery_email_preview(email)
    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )

"""
HTTP endpoints for boxes.

Controllers stay deliberately thin: bind the route, take the authenticated
user, call one service method, return its result. Workflow rules live in
`app/services/box_service.py`, and broken rules are turned into status codes
by the handlers in `app/api/errors.py`.
"""

import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import BoxServiceDep, CurrentUser
from app.models import (
    BoxCreate,
    BoxesPublic,
    BoxPublic,
    BoxStage,
    BoxUpdate,
    Message,
)

router = APIRouter(prefix="/boxes", tags=["boxes"])


@router.get("/", response_model=BoxesPublic)
def read_boxes(
    service: BoxServiceDep,
    current_user: CurrentUser,
    stage: BoxStage | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve boxes.

    Optionally filtered to a single pipeline stage, and/or narrowed to
    boxes whose name contains `q` (ignoring capitalisation).
    """
    return service.list_boxes(stage=stage, q=q, skip=skip, limit=limit)


@router.get("/{id}", response_model=BoxPublic)
def read_box(service: BoxServiceDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get box by ID.
    """
    return service.get_box(id)


@router.post("/", response_model=BoxPublic)
def create_box(
    *, service: BoxServiceDep, current_user: CurrentUser, box_in: BoxCreate
) -> Any:
    """
    Create new box. New boxes enter the pipeline at preparation.
    """
    return service.create_box(box_in, current_user)


@router.put("/{id}", response_model=BoxPublic)
def update_box(
    *,
    service: BoxServiceDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    box_in: BoxUpdate,
) -> Any:
    """
    Update a box. Owner or superuser only.
    """
    return service.update_box(id, box_in, current_user)


@router.post("/{id}/claim", response_model=BoxPublic)
def claim_box(service: BoxServiceDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Claim a box for yourself. A user may hold only one box at a time.
    """
    return service.claim(id, current_user)


@router.post("/{id}/unclaim", response_model=BoxPublic)
def unclaim_box(
    service: BoxServiceDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Release a box you have claimed. Superusers may release any box.
    """
    return service.release(id, current_user)


@router.post("/{id}/reject", response_model=BoxPublic)
def reject_box(service: BoxServiceDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Send a box back one stage because problems were found.

    Clears the records for both the current stage (partial work) and the
    stage being returned to, so that work is genuinely redone, and
    releases the box back to the pool.
    """
    return service.send_back(id, current_user)


@router.delete("/{id}")
def delete_box(
    service: BoxServiceDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a box. Superusers only.
    """
    service.delete_box(id, current_user)
    return Message(message="Box deleted successfully")

"""
HTTP endpoints for docs.

Docs are nested under their box for listing and creation, but addressed
directly by id once they exist. All rules live in
`app/services/doc_service.py`.
"""

import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DocServiceDep
from app.models import DocCreate, DocPublic, DocsPublic, DocUpdate, Message

router = APIRouter(tags=["docs"])


@router.get("/boxes/{box_id}/docs/", response_model=DocsPublic)
def read_docs(
    service: DocServiceDep, current_user: CurrentUser, box_id: uuid.UUID
) -> Any:
    """
    Retrieve docs for a box. Visible to any authenticated user.
    """
    return service.list_for_box(box_id)


@router.post("/boxes/{box_id}/docs/", response_model=DocPublic)
def create_doc(
    *,
    service: DocServiceDep,
    current_user: CurrentUser,
    box_id: uuid.UUID,
    doc_in: DocCreate,
) -> Any:
    """
    Create a new doc inside a box.
    """
    return service.create_doc(box_id, doc_in, current_user)


@router.get("/docs/{id}", response_model=DocPublic)
def read_doc(service: DocServiceDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get doc by ID.
    """
    return service.get_doc(id)


@router.put("/docs/{id}", response_model=DocPublic)
def update_doc(
    *,
    service: DocServiceDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    doc_in: DocUpdate,
) -> Any:
    """
    Update a doc.

    `completed` applies to the stage the box is currently in: it records
    who did the work and when, and advances the box once every doc is done.
    """
    return service.update_doc(id, doc_in, current_user)


@router.delete("/docs/{id}")
def delete_doc(
    service: DocServiceDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a doc. Superusers only.
    """
    service.delete_doc(id, current_user)
    return Message(message="Doc deleted successfully")

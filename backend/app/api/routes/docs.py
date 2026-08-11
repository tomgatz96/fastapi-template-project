import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.boxes import display_name, is_box_completed
from app.models import (
    Box,
    Doc,
    DocCreate,
    DocPublic,
    DocsPublic,
    DocUpdate,
    Message,
    User,
)

router = APIRouter(tags=["docs"])


def _to_public(doc: Doc) -> DocPublic:
    return DocPublic(
        id=doc.id,
        name=doc.name,
        description=doc.description,
        completed=doc.completed,
        pages=doc.pages,
        box_id=doc.box_id,
        completed_at=doc.completed_at,
        completed_by_id=doc.completed_by_id,
        completed_by_name=display_name(doc.completed_by),
    )


def _get_box(session: SessionDep, box_id: uuid.UUID) -> Box:
    box = session.get(Box, box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    return box


def _get_doc(session: SessionDep, id: uuid.UUID) -> Doc:
    doc = session.get(Doc, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    return doc


def _require_edit_access(box: Box, current_user: User) -> None:
    """
    An unclaimed box is open for anyone to set up.
    A claimed box may only be edited by its holder (or a superuser).
    """
    if current_user.is_superuser:
        return
    if box.assignee_id is None:
        return
    if box.assignee_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="This box is claimed by another user",
        )


def _require_completion_access(box: Box, current_user: User) -> None:
    """
    Completing work requires holding the box.
    """
    if current_user.is_superuser:
        return
    if box.assignee_id is None:
        raise HTTPException(
            status_code=403,
            detail="Claim this box before completing its docs",
        )
    if box.assignee_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="This box is claimed by another user",
        )


def _release_box_if_finished(session: SessionDep, box: Box) -> None:
    """
    Finishing the last outstanding doc releases the box back to the pool.
    """
    session.refresh(box)
    if box.assignee_id is not None and is_box_completed(box):
        box.assignee_id = None
        session.add(box)
        session.commit()


@router.get("/boxes/{box_id}/docs/", response_model=DocsPublic)
def read_docs(session: SessionDep, current_user: CurrentUser, box_id: uuid.UUID) -> Any:
    """
    Retrieve docs for a box. Visible to any authenticated user.
    """
    _get_box(session, box_id)
    docs = session.exec(select(Doc).where(Doc.box_id == box_id)).all()
    return DocsPublic(data=[_to_public(d) for d in docs], count=len(docs))


@router.post("/boxes/{box_id}/docs/", response_model=DocPublic)
def create_doc(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    box_id: uuid.UUID,
    doc_in: DocCreate,
) -> Any:
    """
    Create a new doc inside a box.
    """
    box = _get_box(session, box_id)
    _require_edit_access(box, current_user)

    data = doc_in.model_dump()
    if data.get("completed"):
        _require_completion_access(box, current_user)
        data["completed_at"] = datetime.now(UTC)
        data["completed_by_id"] = current_user.id

    doc = Doc.model_validate(data, update={"box_id": box_id})
    session.add(doc)
    session.commit()
    session.refresh(doc)
    _release_box_if_finished(session, box)
    return _to_public(doc)


@router.get("/docs/{id}", response_model=DocPublic)
def read_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get doc by ID.
    """
    return _to_public(_get_doc(session, id))


@router.put("/docs/{id}", response_model=DocPublic)
def update_doc(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    doc_in: DocUpdate,
) -> Any:
    """
    Update a doc.

    Marking a doc completed records who did it and when, and releases the
    box if this was the last outstanding doc.
    """
    doc = _get_doc(session, id)
    box = _get_box(session, doc.box_id)
    _require_edit_access(box, current_user)

    update_dict = doc_in.model_dump(exclude_unset=True)

    if "completed" in update_dict and update_dict["completed"] != doc.completed:
        _require_completion_access(box, current_user)
        if update_dict["completed"]:
            update_dict["completed_at"] = datetime.now(UTC)
            update_dict["completed_by_id"] = current_user.id
        else:
            update_dict["completed_at"] = None
            update_dict["completed_by_id"] = None

    doc.sqlmodel_update(update_dict)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    _release_box_if_finished(session, box)
    return _to_public(doc)


@router.delete("/docs/{id}")
def delete_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Message:
    """
    Delete a doc. Superusers only.
    """
    doc = _get_doc(session, id)
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(doc)
    session.commit()
    return Message(message="Doc deleted successfully")

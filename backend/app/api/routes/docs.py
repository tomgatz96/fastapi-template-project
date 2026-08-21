import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.boxes import (
    STAGE_FIELDS,
    display_name,
    doc_done_in_stage,
    is_stage_finished,
    next_stage,
)
from app.models import (
    Box,
    BoxStage,
    Doc,
    DocCreate,
    DocPublic,
    DocsPublic,
    DocUpdate,
    Message,
    User,
)

router = APIRouter(tags=["docs"])


def _to_public(doc: Doc, box: Box) -> DocPublic:
    return DocPublic(
        id=doc.id,
        name=doc.name,
        description=doc.description,
        pages=doc.pages,
        box_id=doc.box_id,
        completed=doc_done_in_stage(doc, box.stage),
        prepared_at=doc.prepared_at,
        prepared_by_name=display_name(doc.prepared_by),
        scanned_at=doc.scanned_at,
        scanned_by_name=display_name(doc.scanned_by),
        checked_at=doc.checked_at,
        checked_by_name=display_name(doc.checked_by),
    )


def _get_box(session: SessionDep, box_id: uuid.UUID) -> Box:
    box = session.get(Box, box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    return box


def _ensure_unique_name(
    session: SessionDep, name: str, exclude_id: uuid.UUID | None = None
) -> None:
    """Doc names are unique across the app, ignoring capitalisation."""
    statement = select(Doc).where(func.lower(Doc.name) == name.strip().lower())
    if exclude_id is not None:
        statement = statement.where(Doc.id != exclude_id)
    if session.exec(statement).first() is not None:
        raise HTTPException(
            status_code=409, detail="A doc with this name already exists"
        )


def _get_doc(session: SessionDep, id: uuid.UUID) -> Doc:
    doc = session.get(Doc, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    return doc


def _require_edit_access(box: Box, current_user: User) -> None:
    """Unclaimed boxes are open to set up; claimed ones belong to their holder."""
    if current_user.is_superuser:
        return
    if box.stage == BoxStage.COMPLETED:
        raise HTTPException(
            status_code=403, detail="This box is completed and can no longer be changed"
        )
    if box.assignee_id is None:
        return
    if box.assignee_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="This box is claimed by another user"
        )


def _require_completion_access(box: Box, current_user: User) -> None:
    """Recording work against a stage requires holding the box."""
    if current_user.is_superuser:
        return
    if box.stage == BoxStage.COMPLETED:
        raise HTTPException(
            status_code=403, detail="This box is completed and can no longer be changed"
        )
    if box.assignee_id is None:
        raise HTTPException(
            status_code=403, detail="Claim this box before completing its docs"
        )
    if box.assignee_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="This box is claimed by another user"
        )


def _set_stage_record(
    doc: Doc, stage: BoxStage, user: User | None
) -> None:
    fields = STAGE_FIELDS.get(stage)
    if fields is None:
        return
    at_field, by_field = fields
    if user is None:
        setattr(doc, at_field, None)
        setattr(doc, by_field, None)
    else:
        setattr(doc, at_field, datetime.now(UTC))
        setattr(doc, by_field, user.id)


def _advance_box_if_finished(session: SessionDep, box: Box) -> None:
    """
    Finishing the last outstanding doc moves the box to the next stage
    and releases it back to the pool.
    """
    session.refresh(box)
    if box.stage == BoxStage.COMPLETED:
        return
    if not is_stage_finished(box):
        return
    upcoming = next_stage(box.stage)
    if upcoming is None:
        return
    box.stage = upcoming
    box.assignee_id = None
    session.add(box)
    session.commit()


@router.get("/boxes/{box_id}/docs/", response_model=DocsPublic)
def read_docs(session: SessionDep, current_user: CurrentUser, box_id: uuid.UUID) -> Any:
    """
    Retrieve docs for a box. Visible to any authenticated user.
    """
    box = _get_box(session, box_id)
    docs = session.exec(select(Doc).where(Doc.box_id == box_id)).all()
    return DocsPublic(data=[_to_public(d, box) for d in docs], count=len(docs))


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

    name = doc_in.name.strip()
    _ensure_unique_name(session, name)
    doc = Doc.model_validate(doc_in, update={"box_id": box_id, "name": name})
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _to_public(doc, box)


@router.get("/docs/{id}", response_model=DocPublic)
def read_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get doc by ID.
    """
    doc = _get_doc(session, id)
    return _to_public(doc, _get_box(session, doc.box_id))


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

    `completed` applies to the stage the box is currently in: it records
    who did the work and when, and advances the box once every doc is done.
    """
    doc = _get_doc(session, id)
    box = _get_box(session, doc.box_id)
    _require_edit_access(box, current_user)

    update_dict = doc_in.model_dump(exclude_unset=True)
    completed = update_dict.pop("completed", None)

    if "name" in update_dict and update_dict["name"] is not None:
        update_dict["name"] = update_dict["name"].strip()
        _ensure_unique_name(session, update_dict["name"], exclude_id=doc.id)

    if completed is not None and completed != doc_done_in_stage(doc, box.stage):
        _require_completion_access(box, current_user)
        _set_stage_record(doc, box.stage, current_user if completed else None)

    doc.sqlmodel_update(update_dict)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    _advance_box_if_finished(session, box)
    session.refresh(box)
    return _to_public(doc, box)


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

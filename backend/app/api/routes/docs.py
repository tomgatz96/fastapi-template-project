import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
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


def _display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.full_name or user.email


def _to_public(doc: Doc) -> DocPublic:
    return DocPublic(
        id=doc.id,
        name=doc.name,
        description=doc.description,
        completed=doc.completed,
        pages=doc.pages,
        box_id=doc.box_id,
        assignee_id=doc.assignee_id,
        assignee_name=_display_name(doc.assignee),
    )


def _get_box(session: SessionDep, box_id: uuid.UUID) -> Box:
    """Boxes are shared: any authenticated user may read or add docs."""
    box = session.get(Box, box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    return box


def _get_doc(session: SessionDep, id: uuid.UUID) -> Doc:
    doc = session.get(Doc, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    return doc


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
    Create a new doc inside a box. Any authenticated user may add docs.
    """
    _get_box(session, box_id)
    doc = Doc.model_validate(doc_in, update={"box_id": box_id})
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _to_public(doc)


@router.get("/docs/{id}", response_model=DocPublic)
def read_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get doc by ID.
    """
    doc = _get_doc(session, id)
    return _to_public(doc)


@router.put("/docs/{id}", response_model=DocPublic)
def update_doc(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    doc_in: DocUpdate,
) -> Any:
    """
    Update a doc. Any authenticated user may edit docs in a shared box.

    Note: the assignee cannot be changed here. Use /docs/{id}/claim
    and /docs/{id}/unclaim instead.
    """
    doc = _get_doc(session, id)
    update_dict = doc_in.model_dump(exclude_unset=True)
    doc.sqlmodel_update(update_dict)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _to_public(doc)


@router.post("/docs/{id}/claim", response_model=DocPublic)
def claim_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Claim a doc for yourself. A user can only ever assign a doc to
    themselves, never to somebody else.
    """
    doc = _get_doc(session, id)
    if doc.assignee_id is not None and doc.assignee_id != current_user.id:
        raise HTTPException(
            status_code=409, detail="This doc is already claimed by another user"
        )
    doc.assignee_id = current_user.id
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return _to_public(doc)


@router.post("/docs/{id}/unclaim", response_model=DocPublic)
def unclaim_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Release a doc you have claimed. Superusers may release any doc.
    """
    doc = _get_doc(session, id)
    if doc.assignee_id is None:
        raise HTTPException(status_code=409, detail="This doc is not claimed")
    if not current_user.is_superuser and doc.assignee_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can only release a doc assigned to you"
        )
    doc.assignee_id = None
    session.add(doc)
    session.commit()
    session.refresh(doc)
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

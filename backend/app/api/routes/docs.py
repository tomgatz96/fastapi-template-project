import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import Box, Doc, DocCreate, DocPublic, DocsPublic, DocUpdate, Message

router = APIRouter(tags=["docs"])


def _get_owned_box(session: SessionDep, current_user: CurrentUser, box_id: uuid.UUID) -> Box:
    box = session.get(Box, box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if not current_user.is_superuser and (box.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return box


@router.get("/boxes/{box_id}/docs/", response_model=DocsPublic)
def read_docs(session: SessionDep, current_user: CurrentUser, box_id: uuid.UUID) -> Any:
    """
    Retrieve docs for a box.
    """
    _get_owned_box(session, current_user, box_id)
    docs = session.exec(select(Doc).where(Doc.box_id == box_id)).all()
    return DocsPublic(data=docs, count=len(docs))


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
    _get_owned_box(session, current_user, box_id)
    doc = Doc.model_validate(doc_in, update={"box_id": box_id})
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.get("/docs/{id}", response_model=DocPublic)
def read_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get doc by ID.
    """
    doc = session.get(Doc, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    _get_owned_box(session, current_user, doc.box_id)
    return doc


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
    """
    doc = session.get(Doc, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    _get_owned_box(session, current_user, doc.box_id)
    update_dict = doc_in.model_dump(exclude_unset=True)
    doc.sqlmodel_update(update_dict)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/docs/{id}")
def delete_doc(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Message:
    """
    Delete a doc.
    """
    doc = session.get(Doc, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    _get_owned_box(session, current_user, doc.box_id)
    session.delete(doc)
    session.commit()
    return Message(message="Doc deleted successfully")
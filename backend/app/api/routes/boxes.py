import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Box, BoxCreate, BoxesPublic, BoxPublic, BoxUpdate, Message

router = APIRouter(prefix="/boxes", tags=["boxes"])


def _to_public(box: Box) -> BoxPublic:
    docs = box.docs
    completed = bool(docs) and all(d.completed for d in docs)
    owner = box.owner
    return BoxPublic(
        id=box.id,
        name=box.name,
        description=box.description,
        owner_id=box.owner_id,
        owner_name=(owner.full_name or owner.email) if owner else None,
        doc_count=len(docs),
        total_pages=sum(d.pages for d in docs),
        completed=completed,
    )


@router.get("/", response_model=BoxesPublic)
def read_boxes(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve boxes. Boxes are shared: every authenticated user sees all boxes.
    """
    count_statement = select(func.count()).select_from(Box)
    count = session.exec(count_statement).one()
    statement = select(Box).offset(skip).limit(limit)
    boxes = session.exec(statement).all()

    return BoxesPublic(data=[_to_public(b) for b in boxes], count=count)


@router.get("/{id}", response_model=BoxPublic)
def read_box(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get box by ID.
    """
    box = session.get(Box, id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    return _to_public(box)


@router.post("/", response_model=BoxPublic)
def create_box(
    *, session: SessionDep, current_user: CurrentUser, box_in: BoxCreate
) -> Any:
    """
    Create new box.
    """
    box = Box.model_validate(box_in, update={"owner_id": current_user.id})
    session.add(box)
    session.commit()
    session.refresh(box)
    return _to_public(box)


@router.put("/{id}", response_model=BoxPublic)
def update_box(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    box_in: BoxUpdate,
) -> Any:
    """
    Update a box.
    """
    box = session.get(Box, id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if not current_user.is_superuser and (box.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = box_in.model_dump(exclude_unset=True)
    box.sqlmodel_update(update_dict)
    session.add(box)
    session.commit()
    session.refresh(box)
    return _to_public(box)


@router.delete("/{id}")
def delete_box(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Message:
    """
    Delete a box.
    """
    box = session.get(Box, id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(box)  # cascades to docs (Box.docs has cascade_delete=True)
    session.commit()
    return Message(message="Box deleted successfully")
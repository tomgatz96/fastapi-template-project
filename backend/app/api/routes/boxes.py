import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Box,
    BoxCreate,
    BoxesPublic,
    BoxPublic,
    BoxUpdate,
    Message,
    User,
)

router = APIRouter(prefix="/boxes", tags=["boxes"])


def display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.full_name or user.email


def is_box_completed(box: Box) -> bool:
    """A box is completed when it holds at least one doc and all are done."""
    return bool(box.docs) and all(d.completed for d in box.docs)


def _to_public(box: Box) -> BoxPublic:
    docs = box.docs
    return BoxPublic(
        id=box.id,
        name=box.name,
        description=box.description,
        owner_id=box.owner_id,
        owner_name=display_name(box.owner),
        assignee_id=box.assignee_id,
        assignee_name=display_name(box.assignee),
        doc_count=len(docs),
        total_pages=sum(d.pages for d in docs),
        completed=is_box_completed(box),
    )


def _get_box(session: SessionDep, id: uuid.UUID) -> Box:
    box = session.get(Box, id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    return box


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
    return _to_public(_get_box(session, id))


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
    Update a box. Owner or superuser only.
    """
    box = _get_box(session, id)
    if not current_user.is_superuser and (box.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = box_in.model_dump(exclude_unset=True)
    box.sqlmodel_update(update_dict)
    session.add(box)
    session.commit()
    session.refresh(box)
    return _to_public(box)


@router.post("/{id}/claim", response_model=BoxPublic)
def claim_box(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Claim a box for yourself.

    A user may hold only one box at a time, and a box may be held by
    only one user. A user can only ever claim a box for themselves.
    """
    box = _get_box(session, id)

    if box.assignee_id == current_user.id:
        return _to_public(box)

    if box.assignee_id is not None:
        raise HTTPException(
            status_code=409, detail="This box is already claimed by another user"
        )

    if is_box_completed(box):
        raise HTTPException(
            status_code=409, detail="This box is already completed"
        )

    existing = session.exec(
        select(Box).where(Box.assignee_id == current_user.id)
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="You already have a box claimed. Release it before claiming another.",
        )

    box.assignee_id = current_user.id
    session.add(box)
    session.commit()
    session.refresh(box)
    return _to_public(box)


@router.post("/{id}/unclaim", response_model=BoxPublic)
def unclaim_box(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Release a box you have claimed. Superusers may release any box.
    """
    box = _get_box(session, id)
    if box.assignee_id is None:
        raise HTTPException(status_code=409, detail="This box is not claimed")
    if not current_user.is_superuser and box.assignee_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can only release a box assigned to you"
        )
    box.assignee_id = None
    session.add(box)
    session.commit()
    session.refresh(box)
    return _to_public(box)


@router.delete("/{id}")
def delete_box(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Message:
    """
    Delete a box. Superusers only.
    """
    box = _get_box(session, id)
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(box)
    session.commit()
    return Message(message="Box deleted successfully")

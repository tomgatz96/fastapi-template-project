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
    BoxStage,
    BoxUpdate,
    Doc,
    Message,
    User,
)

router = APIRouter(prefix="/boxes", tags=["boxes"])

# The pipeline, in order. A box moves forward one step at a time.
STAGE_ORDER: list[BoxStage] = [
    BoxStage.PREPARATION,
    BoxStage.SCAN,
    BoxStage.QUALITY_CONTROL,
    BoxStage.COMPLETED,
]

# Which pair of Doc columns records the work done in each stage.
STAGE_FIELDS: dict[BoxStage, tuple[str, str]] = {
    BoxStage.PREPARATION: ("prepared_at", "prepared_by_id"),
    BoxStage.SCAN: ("scanned_at", "scanned_by_id"),
    BoxStage.QUALITY_CONTROL: ("checked_at", "checked_by_id"),
}


def display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.full_name or user.email


def next_stage(stage: BoxStage) -> BoxStage | None:
    index = STAGE_ORDER.index(stage)
    if index + 1 >= len(STAGE_ORDER):
        return None
    return STAGE_ORDER[index + 1]


def previous_stage(stage: BoxStage) -> BoxStage | None:
    index = STAGE_ORDER.index(stage)
    if index == 0:
        return None
    return STAGE_ORDER[index - 1]


def doc_done_in_stage(doc: Doc, stage: BoxStage) -> bool:
    fields = STAGE_FIELDS.get(stage)
    if fields is None:
        return True
    return getattr(doc, fields[0]) is not None


def clear_stage_records(doc: Doc, stage: BoxStage) -> None:
    fields = STAGE_FIELDS.get(stage)
    if fields is None:
        return
    setattr(doc, fields[0], None)
    setattr(doc, fields[1], None)


def stage_done_count(box: Box) -> int:
    return sum(1 for d in box.docs if doc_done_in_stage(d, box.stage))


def is_stage_finished(box: Box) -> bool:
    """A stage is finished when the box holds docs and all are done for it."""
    if box.stage == BoxStage.COMPLETED:
        return True
    return bool(box.docs) and all(doc_done_in_stage(d, box.stage) for d in box.docs)


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
        stage=box.stage,
        doc_count=len(docs),
        stage_done_count=stage_done_count(box),
        total_pages=sum(d.pages for d in docs),
        completed=box.stage == BoxStage.COMPLETED,
    )


def _ensure_unique_name(
    session: SessionDep, name: str, exclude_id: uuid.UUID | None = None
) -> None:
    """Box names are unique across the app, ignoring capitalisation."""
    statement = select(Box).where(func.lower(Box.name) == name.strip().lower())
    if exclude_id is not None:
        statement = statement.where(Box.id != exclude_id)
    if session.exec(statement).first() is not None:
        raise HTTPException(
            status_code=409, detail="A box with this name already exists"
        )


def _get_box(session: SessionDep, id: uuid.UUID) -> Box:
    box = session.get(Box, id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    return box


@router.get("/", response_model=BoxesPublic)
def read_boxes(
    session: SessionDep,
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
    count_statement = select(func.count()).select_from(Box)
    statement = select(Box)

    if stage is not None:
        count_statement = count_statement.where(Box.stage == stage)
        statement = statement.where(Box.stage == stage)

    if q is not None and q.strip():
        pattern = f"%{q.strip().lower()}%"
        count_statement = count_statement.where(func.lower(Box.name).like(pattern))
        statement = statement.where(func.lower(Box.name).like(pattern))

    count = session.exec(count_statement).one()
    boxes = session.exec(statement.order_by(Box.name).offset(skip).limit(limit)).all()
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
    Create new box. New boxes enter the pipeline at preparation.
    """
    name = box_in.name.strip()
    _ensure_unique_name(session, name)
    box = Box.model_validate(box_in, update={"owner_id": current_user.id, "name": name})
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
    if "name" in update_dict and update_dict["name"] is not None:
        update_dict["name"] = update_dict["name"].strip()
        _ensure_unique_name(session, update_dict["name"], exclude_id=box.id)
    box.sqlmodel_update(update_dict)
    session.add(box)
    session.commit()
    session.refresh(box)
    return _to_public(box)


@router.post("/{id}/claim", response_model=BoxPublic)
def claim_box(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Claim a box for yourself. A user may hold only one box at a time.
    """
    box = _get_box(session, id)

    if box.assignee_id == current_user.id:
        return _to_public(box)

    if box.assignee_id is not None:
        raise HTTPException(
            status_code=409, detail="This box is already claimed by another user"
        )

    if box.stage == BoxStage.COMPLETED:
        raise HTTPException(status_code=409, detail="This box is already completed")

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


@router.post("/{id}/reject", response_model=BoxPublic)
def reject_box(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Send a box back one stage because problems were found.

    Clears the records for both the current stage (partial work) and the
    stage being returned to, so that work is genuinely redone, and
    releases the box back to the pool.
    """
    box = _get_box(session, id)

    previous = previous_stage(box.stage)
    if previous is None:
        raise HTTPException(
            status_code=409, detail="Preparation is the first stage, nothing to go back to"
        )
    if box.stage == BoxStage.COMPLETED:
        raise HTTPException(
            status_code=409, detail="This box is already completed"
        )
    if not current_user.is_superuser and box.assignee_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Claim this box before sending it back"
        )

    for doc in box.docs:
        clear_stage_records(doc, box.stage)
        clear_stage_records(doc, previous)
        session.add(doc)

    box.stage = previous
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

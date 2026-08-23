"""
Box workflow rules.

This is where the application's actual decisions live: who may edit a box,
when a box can be claimed, what sending one back means. The service receives
domain objects, decides, and hands persistence to the repository. It reports
broken rules with domain exceptions, never HTTP status codes.
"""

import uuid

from app.models import (
    Box,
    BoxCreate,
    BoxesPublic,
    BoxPublic,
    BoxStage,
    BoxUpdate,
    User,
    display_name,
)
from app.repositories.box_repository import BoxRepository
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.services.pipeline import (
    clear_stage_records,
    previous_stage,
    stage_done_count,
)


class BoxService:
    def __init__(self, boxes: BoxRepository) -> None:
        self.boxes = boxes

    # --- queries ---

    def list_boxes(
        self,
        *,
        stage: BoxStage | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> BoxesPublic:
        """
        Boxes in the pipeline.

        Optionally filtered to a single stage, and/or narrowed to boxes whose
        name contains `q` (ignoring capitalisation).
        """
        boxes = self.boxes.list(stage=stage, q=q, skip=skip, limit=limit)
        count = self.boxes.count(stage=stage, q=q)
        return BoxesPublic(data=[self.to_public(b) for b in boxes], count=count)

    def get_box(self, box_id: uuid.UUID) -> BoxPublic:
        return self.to_public(self._require_box(box_id))

    # --- commands ---

    def create_box(self, box_in: BoxCreate, owner: User) -> BoxPublic:
        """New boxes enter the pipeline at preparation."""
        name = box_in.name.strip()
        self._require_unique_name(name)
        box = Box.model_validate(box_in, update={"owner_id": owner.id, "name": name})
        return self.to_public(self.boxes.save(box))

    def update_box(
        self, box_id: uuid.UUID, box_in: BoxUpdate, current_user: User
    ) -> BoxPublic:
        """Only the owner, or a superuser, may change a box's details."""
        box = self._require_box(box_id)
        if not current_user.is_superuser and box.owner_id != current_user.id:
            raise PermissionDeniedError("Not enough permissions")

        update_dict = box_in.model_dump(exclude_unset=True)
        if "name" in update_dict and update_dict["name"] is not None:
            update_dict["name"] = update_dict["name"].strip()
            self._require_unique_name(update_dict["name"], exclude_id=box.id)

        box.sqlmodel_update(update_dict)
        return self.to_public(self.boxes.save(box))

    def claim(self, box_id: uuid.UUID, user: User) -> BoxPublic:
        """
        Take a box out of the shared pool.

        A user may hold only one box at a time. Claiming a box you already
        hold is a no-op rather than an error, so a double click is harmless.
        """
        box = self._require_box(box_id)

        if box.assignee_id == user.id:
            return self.to_public(box)

        if box.assignee_id is not None:
            raise ConflictError("This box is already claimed by another user")

        if box.stage == BoxStage.COMPLETED:
            raise ConflictError("This box is already completed")

        if self.boxes.find_claimed_by(user.id) is not None:
            raise ConflictError(
                "You already have a box claimed. Release it before claiming another."
            )

        box.assignee_id = user.id
        return self.to_public(self.boxes.save(box))

    def release(self, box_id: uuid.UUID, user: User) -> BoxPublic:
        """Put a claimed box back in the pool. Superusers may release any box."""
        box = self._require_box(box_id)

        if box.assignee_id is None:
            raise ConflictError("This box is not claimed")

        if not user.is_superuser and box.assignee_id != user.id:
            raise PermissionDeniedError("You can only release a box assigned to you")

        box.assignee_id = None
        return self.to_public(self.boxes.save(box))

    def send_back(self, box_id: uuid.UUID, user: User) -> BoxPublic:
        """
        Return a box one stage because problems were found.

        Clears the records for both the current stage (partial work) and the
        stage being returned to, so that work is genuinely redone, and
        releases the box back to the pool.
        """
        box = self._require_box(box_id)

        previous = previous_stage(box.stage)
        if previous is None:
            raise ConflictError(
                "Preparation is the first stage, nothing to go back to"
            )

        if box.stage == BoxStage.COMPLETED:
            raise ConflictError("This box is already completed")

        if not user.is_superuser and box.assignee_id != user.id:
            raise PermissionDeniedError("Claim this box before sending it back")

        for doc in box.docs:
            clear_stage_records(doc, box.stage)
            clear_stage_records(doc, previous)

        box.stage = previous
        box.assignee_id = None
        return self.to_public(self.boxes.save(box))

    def delete_box(self, box_id: uuid.UUID, user: User) -> None:
        """Deleting a box destroys its docs too, so it is superuser only."""
        box = self._require_box(box_id)
        if not user.is_superuser:
            raise PermissionDeniedError("Not enough permissions")
        self.boxes.delete(box)

    # --- internals ---

    def _require_box(self, box_id: uuid.UUID) -> Box:
        box = self.boxes.get(box_id)
        if box is None:
            raise NotFoundError("Box not found")
        return box

    def _require_unique_name(
        self, name: str, *, exclude_id: uuid.UUID | None = None
    ) -> None:
        """Box names are unique across the app, ignoring capitalisation."""
        if self.boxes.find_by_name(name, exclude_id=exclude_id) is not None:
            raise ConflictError("A box with this name already exists")

    @staticmethod
    def to_public(box: Box) -> BoxPublic:
        """Add the counters derived from the box's docs."""
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

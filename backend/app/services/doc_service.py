"""
Doc rules.

A doc only exists inside a box, and what may be done to it depends entirely
on that box: who is holding it, which stage it is in, whether it is
finished. So this service works with both repositories — the doc's own, and
the box's, for the access checks and for the promotion that finishing the
last doc triggers.
"""

import uuid

from app.models import (
    Box,
    BoxStage,
    Doc,
    DocCreate,
    DocPublic,
    DocsPublic,
    DocUpdate,
    User,
    display_name,
)
from app.repositories.box_repository import BoxRepository
from app.repositories.doc_repository import DocRepository
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.services.pipeline import (
    advance_if_finished,
    doc_done_in_stage,
    set_stage_record,
)


class DocService:
    def __init__(self, docs: DocRepository, boxes: BoxRepository) -> None:
        self.docs = docs
        self.boxes = boxes

    # --- queries ---

    def list_for_box(self, box_id: uuid.UUID) -> DocsPublic:
        """Docs inside a box. Visible to any authenticated user."""
        box = self._require_box(box_id)
        docs = self.docs.list_for_box(box_id)
        return DocsPublic(
            data=[self.to_public(d, box) for d in docs], count=len(docs)
        )

    def get_doc(self, doc_id: uuid.UUID) -> DocPublic:
        doc = self._require_doc(doc_id)
        return self.to_public(doc, self._require_box(doc.box_id))

    # --- commands ---

    def create_doc(
        self, box_id: uuid.UUID, doc_in: DocCreate, current_user: User
    ) -> DocPublic:
        """Add a doc to a box."""
        box = self._require_box(box_id)
        self._require_edit_access(box, current_user)

        name = doc_in.name.strip()
        self._require_unique_name(name)
        doc = Doc.model_validate(doc_in, update={"box_id": box_id, "name": name})
        return self.to_public(self.docs.save(doc), box)

    def update_doc(
        self, doc_id: uuid.UUID, doc_in: DocUpdate, current_user: User
    ) -> DocPublic:
        """
        Update a doc.

        `completed` applies to the stage the box is currently in: it records
        who did the work and when, and advances the box once every doc is
        done. Editing a doc's details only needs edit access, but recording
        work against a stage means holding the box, so the stricter check
        applies solely when `completed` actually changes.
        """
        doc = self._require_doc(doc_id)
        box = self._require_box(doc.box_id)
        self._require_edit_access(box, current_user)

        update_dict = doc_in.model_dump(exclude_unset=True)
        completed = update_dict.pop("completed", None)

        if "name" in update_dict and update_dict["name"] is not None:
            update_dict["name"] = update_dict["name"].strip()
            self._require_unique_name(update_dict["name"], exclude_id=doc.id)

        if completed is not None and completed != doc_done_in_stage(doc, box.stage):
            self._require_completion_access(box, current_user)
            set_stage_record(doc, box.stage, current_user if completed else None)

        doc.sqlmodel_update(update_dict)
        self.docs.save(doc)

        # The box has to be reloaded before it is asked whether its stage is
        # finished, because the doc that may have finished it was just saved.
        self.boxes.refresh(box)
        if advance_if_finished(box):
            self.boxes.save(box)
        self.boxes.refresh(box)

        return self.to_public(doc, box)

    def delete_doc(self, doc_id: uuid.UUID, current_user: User) -> None:
        """Deleting a doc discards its audit trail, so it is superuser only."""
        doc = self._require_doc(doc_id)
        if not current_user.is_superuser:
            raise PermissionDeniedError("Not enough permissions")
        self.docs.delete(doc)

    # --- access rules ---

    @staticmethod
    def _require_edit_access(box: Box, current_user: User) -> None:
        """Unclaimed boxes are open to set up; claimed ones belong to their holder."""
        if current_user.is_superuser:
            return
        if box.stage == BoxStage.COMPLETED:
            raise PermissionDeniedError(
                "This box is completed and can no longer be changed"
            )
        if box.assignee_id is None:
            return
        if box.assignee_id != current_user.id:
            raise PermissionDeniedError("This box is claimed by another user")

    @staticmethod
    def _require_completion_access(box: Box, current_user: User) -> None:
        """Recording work against a stage requires holding the box."""
        if current_user.is_superuser:
            return
        if box.stage == BoxStage.COMPLETED:
            raise PermissionDeniedError(
                "This box is completed and can no longer be changed"
            )
        if box.assignee_id is None:
            raise PermissionDeniedError("Claim this box before completing its docs")
        if box.assignee_id != current_user.id:
            raise PermissionDeniedError("This box is claimed by another user")

    # --- internals ---

    def _require_doc(self, doc_id: uuid.UUID) -> Doc:
        doc = self.docs.get(doc_id)
        if doc is None:
            raise NotFoundError("Doc not found")
        return doc

    def _require_box(self, box_id: uuid.UUID) -> Box:
        box = self.boxes.get(box_id)
        if box is None:
            raise NotFoundError("Box not found")
        return box

    def _require_unique_name(
        self, name: str, *, exclude_id: uuid.UUID | None = None
    ) -> None:
        """Doc names are unique across the app, ignoring capitalisation."""
        if self.docs.find_by_name(name, exclude_id=exclude_id) is not None:
            raise ConflictError("A doc with this name already exists")

    @staticmethod
    def to_public(doc: Doc, box: Box) -> DocPublic:
        """`completed` is relative to the box's current stage, so the box is needed."""
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

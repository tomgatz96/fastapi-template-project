"""
Database access for boxes.

Box is the aggregate root: a Doc only exists inside a Box, so persisting a
box through this repository also persists the docs loaded with it. Nothing
outside this module writes box SQL, and nothing inside it knows about users,
permissions or HTTP.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, func, select

from app.models import Box, BoxStage


class BoxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- queries ---

    def get(self, box_id: uuid.UUID) -> Box | None:
        """The box with this id, or None."""
        return self.session.get(Box, box_id)

    def list(
        self,
        *,
        stage: BoxStage | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Box]:
        """Boxes ordered by name, optionally filtered by stage and name."""
        statement = self._apply_filters(select(Box), stage=stage, q=q)
        statement = statement.order_by(Box.name).offset(skip).limit(limit)
        return self.session.exec(statement).all()

    def count(self, *, stage: BoxStage | None = None, q: str | None = None) -> int:
        """How many boxes match the same filters as `list`."""
        statement = self._apply_filters(
            select(func.count()).select_from(Box), stage=stage, q=q
        )
        return self.session.exec(statement).one()

    def find_by_name(
        self, name: str, *, exclude_id: uuid.UUID | None = None
    ) -> Box | None:
        """A box with this name, ignoring capitalisation."""
        statement = select(Box).where(func.lower(Box.name) == name.strip().lower())
        if exclude_id is not None:
            statement = statement.where(Box.id != exclude_id)
        return self.session.exec(statement).first()

    def find_claimed_by(self, user_id: uuid.UUID) -> Box | None:
        """The box this user is currently holding, if any."""
        return self.session.exec(
            select(Box).where(Box.assignee_id == user_id)
        ).first()

    # --- persistence ---

    def save(self, box: Box) -> Box:
        """Persist the box and any docs modified alongside it."""
        self.session.add(box)
        self.session.commit()
        self.session.refresh(box)
        return box

    def refresh(self, box: Box) -> Box:
        """
        Reload the box from the database.

        Needed after a doc inside it has been written, so that the box's
        view of its own docs reflects the change before it is inspected.
        """
        self.session.refresh(box)
        return box

    def delete(self, box: Box) -> None:
        """Remove the box; its docs cascade."""
        self.session.delete(box)
        self.session.commit()

    # --- internals ---

    @staticmethod
    def _apply_filters(
        statement: Any, *, stage: BoxStage | None, q: str | None
    ) -> Any:
        if stage is not None:
            statement = statement.where(Box.stage == stage)
        if q is not None and q.strip():
            pattern = f"%{q.strip().lower()}%"
            statement = statement.where(func.lower(Box.name).like(pattern))
        return statement

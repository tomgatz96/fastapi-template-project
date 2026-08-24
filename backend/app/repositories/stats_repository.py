"""
Database access for the work report.

Read-only, and deliberately narrow: the report needs to know who the users
are, and which docs had work recorded against them since a cutoff. Rows come
back as plain `CompletedWork` tuples so the service never handles result rows,
and the stage-to-column mapping is taken from `pipeline` rather than restated
here, so there is still only one place that knows which columns record which
stage.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from sqlmodel import Session, select

from app.models import BoxStage, Doc, User
from app.services.pipeline import STAGE_FIELDS


class CompletedWork(NamedTuple):
    """One doc finished in one stage: who did it, when, and how big it was."""

    user_id: uuid.UUID | None
    completed_at: datetime
    pages: int


class StatsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- queries ---

    def list_users(self) -> Sequence[User]:
        """
        Every user.

        The report lists people who recorded no work at all, so the roster
        comes from the users table rather than from the work records.
        """
        return self.session.exec(select(User)).all()

    def completed_since(self, stage: BoxStage, since: datetime) -> list[CompletedWork]:
        """
        Work recorded for `stage` at or after `since`.

        A doc with no page count contributes zero pages rather than None, so
        the service can add up totals without guarding every row.
        """
        fields = STAGE_FIELDS.get(stage)
        if fields is None:
            return []

        at_column = getattr(Doc, fields[0])
        by_column = getattr(Doc, fields[1])

        rows = self.session.exec(
            select(by_column, at_column, Doc.pages).where(at_column >= since)
        ).all()

        return [
            CompletedWork(user_id=user_id, completed_at=completed_at, pages=pages or 0)
            for user_id, completed_at, pages in rows
        ]

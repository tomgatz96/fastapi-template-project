"""
Database access for docs.

A doc always belongs to a box, so most reads are scoped by `box_id`. Doc
names, however, are unique across the whole application, which is why
`find_by_name` searches globally rather than within a box.
"""

import uuid
from collections.abc import Sequence

from sqlmodel import Session, func, select

from app.models import Doc


class DocRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- queries ---

    def get(self, doc_id: uuid.UUID) -> Doc | None:
        """The doc with this id, or None."""
        return self.session.get(Doc, doc_id)

    def list_for_box(self, box_id: uuid.UUID) -> Sequence[Doc]:
        """Every doc inside this box."""
        return self.session.exec(select(Doc).where(Doc.box_id == box_id)).all()

    def find_by_name(
        self, name: str, *, exclude_id: uuid.UUID | None = None
    ) -> Doc | None:
        """A doc with this name, ignoring capitalisation."""
        statement = select(Doc).where(func.lower(Doc.name) == name.strip().lower())
        if exclude_id is not None:
            statement = statement.where(Doc.id != exclude_id)
        return self.session.exec(statement).first()

    # --- persistence ---

    def save(self, doc: Doc) -> Doc:
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        return doc

    def delete(self, doc: Doc) -> None:
        self.session.delete(doc)
        self.session.commit()

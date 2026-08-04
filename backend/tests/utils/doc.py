import uuid

from sqlmodel import Session

from app import crud
from app.models import Doc, DocCreate
from tests.utils.box import create_random_box
from tests.utils.utils import random_lower_string


def create_random_doc(db: Session, box_id: uuid.UUID | None = None) -> Doc:
    if box_id is None:
        box_id = create_random_box(db).id
    name = random_lower_string()
    description = random_lower_string()
    doc_in = DocCreate(name=name, description=description)
    return crud.create_doc(session=db, doc_in=doc_in, box_id=box_id)
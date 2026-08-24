from sqlmodel import Session

from app.models import Box, BoxCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_box(db: Session) -> Box:
    user = create_random_user(db)
    owner_id = user.id
    assert owner_id is not None
    name = random_lower_string()
    description = random_lower_string()
    box_in = BoxCreate(name=name, description=description)
    box = Box.model_validate(box_in, update={"owner_id": owner_id})
    db.add(box)
    db.commit()
    db.refresh(box)
    return box

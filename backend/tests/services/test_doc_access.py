"""
Unit tests for the doc access rules.

`_require_edit_access` and `_require_completion_access` are static methods
taking only a box and a user, so they can be checked directly. The
distinction they draw matters: editing a doc's details is open while a box
sits unclaimed, but recording work against a stage means holding the box.
"""

import uuid

import pytest

from app.models import Box, BoxStage, User
from app.services.doc_service import DocService
from app.services.exceptions import PermissionDeniedError

require_edit = DocService._require_edit_access
require_completion = DocService._require_completion_access


def make_user(*, superuser: bool = False) -> User:
    return User(
        email=f"{uuid.uuid4()}@example.com",
        hashed_password="x",
        is_superuser=superuser,
    )


# --- editing a doc ---


def test_an_unclaimed_box_is_open_for_editing() -> None:
    require_edit(Box(name="free", stage=BoxStage.PREPARATION), make_user())


def test_the_holder_may_edit_their_own_box() -> None:
    user = make_user()
    box = Box(name="mine", stage=BoxStage.SCAN, assignee_id=user.id)

    require_edit(box, user)


def test_a_box_claimed_by_someone_else_is_closed() -> None:
    box = Box(name="theirs", stage=BoxStage.SCAN, assignee_id=uuid.uuid4())

    with pytest.raises(PermissionDeniedError, match="claimed by another user"):
        require_edit(box, make_user())


def test_a_completed_box_can_no_longer_be_changed() -> None:
    box = Box(name="finished", stage=BoxStage.COMPLETED)

    with pytest.raises(PermissionDeniedError, match="completed"):
        require_edit(box, make_user())


def test_a_superuser_may_edit_a_completed_box() -> None:
    require_edit(
        Box(name="finished", stage=BoxStage.COMPLETED), make_user(superuser=True)
    )


# --- recording work ---


def test_recording_work_requires_holding_the_box() -> None:
    """The key difference from editing: an unclaimed box is not enough."""
    box = Box(name="free", stage=BoxStage.PREPARATION)

    with pytest.raises(PermissionDeniedError, match="Claim this box"):
        require_completion(box, make_user())


def test_the_holder_may_record_work() -> None:
    user = make_user()
    box = Box(name="mine", stage=BoxStage.SCAN, assignee_id=user.id)

    require_completion(box, user)


def test_recording_work_on_someone_elses_box_is_refused() -> None:
    box = Box(name="theirs", stage=BoxStage.SCAN, assignee_id=uuid.uuid4())

    with pytest.raises(PermissionDeniedError, match="claimed by another user"):
        require_completion(box, make_user())


def test_recording_work_on_a_completed_box_is_refused() -> None:
    box = Box(name="finished", stage=BoxStage.COMPLETED)

    with pytest.raises(PermissionDeniedError, match="completed"):
        require_completion(box, make_user())


def test_a_superuser_may_record_work_on_any_box() -> None:
    box = Box(name="theirs", stage=BoxStage.SCAN, assignee_id=uuid.uuid4())

    require_completion(box, make_user(superuser=True))

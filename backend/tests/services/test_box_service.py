"""
Unit tests for the box workflow, using an in-memory repository.

`BoxService` depends on a repository, not on a `Session`, so a small stand-in
is enough to exercise its rules. This is the practical payoff of the
repository layer: the service can be tested without a database, a migration
or a running server.

The rules that need real SQL — unique names, claiming under concurrency —
stay covered by the API tests, which exercise the actual constraints.
"""

import uuid

import pytest

from app.models import Box, BoxStage, BoxUpdate, Doc, User
from app.services.box_service import BoxService
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)


class FakeBoxRepository:
    """An in-memory stand-in with the same surface the service uses."""

    def __init__(self, *boxes: Box) -> None:
        self.boxes = {b.id: b for b in boxes}
        self.saved: list[Box] = []

    def get(self, box_id: uuid.UUID) -> Box | None:
        return self.boxes.get(box_id)

    def find_by_name(
        self, name: str, *, exclude_id: uuid.UUID | None = None
    ) -> Box | None:
        for box in self.boxes.values():
            if box.name.lower() == name.strip().lower() and box.id != exclude_id:
                return box
        return None

    def find_claimed_by(self, user_id: uuid.UUID) -> Box | None:
        return next((b for b in self.boxes.values() if b.assignee_id == user_id), None)

    def save(self, box: Box) -> Box:
        self.boxes[box.id] = box
        self.saved.append(box)
        return box

    def delete(self, box: Box) -> None:
        del self.boxes[box.id]


def make_user(*, superuser: bool = False) -> User:
    return User(
        email=f"{uuid.uuid4()}@example.com",
        hashed_password="x",
        is_superuser=superuser,
    )


def make_service(*boxes: Box) -> tuple[BoxService, FakeBoxRepository]:
    repo = FakeBoxRepository(*boxes)
    return BoxService(repo), repo  # type: ignore[arg-type]


# --- lookups ---


def test_an_unknown_box_is_not_found() -> None:
    service, _ = make_service()

    with pytest.raises(NotFoundError, match="Box not found"):
        service.get_box(uuid.uuid4())


# --- claiming ---


def test_claiming_a_free_box_assigns_it() -> None:
    box = Box(name="free", stage=BoxStage.PREPARATION)
    service, repo = make_service(box)
    user = make_user()

    service.claim(box.id, user)

    assert box.assignee_id == user.id
    assert repo.saved == [box]


def test_claiming_a_box_you_already_hold_changes_nothing() -> None:
    """Idempotent, so a double click is harmless rather than an error."""
    user = make_user()
    box = Box(name="mine", stage=BoxStage.SCAN, assignee_id=user.id)
    service, repo = make_service(box)

    service.claim(box.id, user)

    assert repo.saved == []


def test_claiming_someone_elses_box_is_refused() -> None:
    box = Box(name="theirs", stage=BoxStage.SCAN, assignee_id=uuid.uuid4())
    service, _ = make_service(box)

    with pytest.raises(ConflictError, match="already claimed"):
        service.claim(box.id, make_user())


def test_a_user_may_hold_only_one_box() -> None:
    user = make_user()
    held = Box(name="held", stage=BoxStage.SCAN, assignee_id=user.id)
    other = Box(name="other", stage=BoxStage.PREPARATION)
    service, _ = make_service(held, other)

    with pytest.raises(ConflictError, match="already have a box"):
        service.claim(other.id, user)


def test_a_completed_box_cannot_be_claimed() -> None:
    box = Box(name="finished", stage=BoxStage.COMPLETED)
    service, _ = make_service(box)

    with pytest.raises(ConflictError, match="already completed"):
        service.claim(box.id, make_user())


# --- releasing ---


def test_releasing_an_unclaimed_box_is_refused() -> None:
    box = Box(name="free", stage=BoxStage.PREPARATION)
    service, _ = make_service(box)

    with pytest.raises(ConflictError, match="not claimed"):
        service.release(box.id, make_user())


def test_only_the_holder_may_release_a_box() -> None:
    box = Box(name="theirs", stage=BoxStage.SCAN, assignee_id=uuid.uuid4())
    service, _ = make_service(box)

    with pytest.raises(PermissionDeniedError, match="assigned to you"):
        service.release(box.id, make_user())


def test_a_superuser_may_release_any_box() -> None:
    box = Box(name="theirs", stage=BoxStage.SCAN, assignee_id=uuid.uuid4())
    service, _ = make_service(box)

    service.release(box.id, make_user(superuser=True))

    assert box.assignee_id is None


# --- sending back ---


def test_sending_back_returns_the_box_a_stage_and_releases_it() -> None:
    user = make_user()
    box = Box(name="rejected", stage=BoxStage.SCAN, assignee_id=user.id)
    doc = Doc(name="d1", box_id=box.id, pages=5, prepared_at=None)
    box.docs = [doc]
    service, _ = make_service(box)

    service.send_back(box.id, user)

    assert box.stage == BoxStage.PREPARATION
    assert box.assignee_id is None


def test_preparation_cannot_be_sent_back() -> None:
    box = Box(name="first", stage=BoxStage.PREPARATION)
    service, _ = make_service(box)

    with pytest.raises(ConflictError, match="first stage"):
        service.send_back(box.id, make_user())


def test_a_completed_box_cannot_be_sent_back() -> None:
    box = Box(name="finished", stage=BoxStage.COMPLETED)
    service, _ = make_service(box)

    with pytest.raises(ConflictError, match="already completed"):
        service.send_back(box.id, make_user(superuser=True))


def test_sending_back_requires_holding_the_box() -> None:
    box = Box(name="theirs", stage=BoxStage.SCAN, assignee_id=uuid.uuid4())
    service, _ = make_service(box)

    with pytest.raises(PermissionDeniedError, match="Claim this box"):
        service.send_back(box.id, make_user())


# --- editing and deleting ---


def test_only_the_owner_may_update_a_box() -> None:
    box = Box(name="theirs", stage=BoxStage.PREPARATION, owner_id=uuid.uuid4())
    service, _ = make_service(box)

    with pytest.raises(PermissionDeniedError, match="Not enough permissions"):
        service.update_box(box.id, BoxUpdate(), make_user())


def test_deleting_a_box_is_superuser_only() -> None:
    box = Box(name="doomed", stage=BoxStage.PREPARATION)
    service, repo = make_service(box)

    with pytest.raises(PermissionDeniedError, match="Not enough permissions"):
        service.delete_box(box.id, make_user())

    service.delete_box(box.id, make_user(superuser=True))
    assert repo.get(box.id) is None

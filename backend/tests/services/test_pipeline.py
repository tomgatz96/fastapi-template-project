"""
Unit tests for the pipeline rules.

These need no database, no HTTP client and no fixtures: `pipeline` is pure
functions over domain objects, so each rule can be stated and checked
directly. That is the point of keeping the stage rules out of the
controllers — before the refactor, reaching these branches meant creating a
box in exactly the right state and driving it through the API.
"""

import uuid
from datetime import UTC, datetime

from app.models import Box, BoxStage, Doc, User
from app.services.pipeline import (
    advance_if_finished,
    clear_stage_records,
    doc_done_in_stage,
    is_stage_finished,
    next_stage,
    previous_stage,
    set_stage_record,
    stage_done_count,
)


def make_user() -> User:
    return User(email="operator@example.com", hashed_password="x")


def make_doc(**kwargs: object) -> Doc:
    return Doc(name=f"doc-{uuid.uuid4()}", box_id=uuid.uuid4(), pages=10, **kwargs)


# --- stage order ---


def test_stages_run_in_pipeline_order() -> None:
    assert next_stage(BoxStage.PREPARATION) == BoxStage.SCAN
    assert next_stage(BoxStage.SCAN) == BoxStage.QUALITY_CONTROL
    assert next_stage(BoxStage.QUALITY_CONTROL) == BoxStage.COMPLETED


def test_nothing_follows_the_last_stage() -> None:
    assert next_stage(BoxStage.COMPLETED) is None


def test_nothing_precedes_the_first_stage() -> None:
    assert previous_stage(BoxStage.PREPARATION) is None


def test_previous_stage_walks_back() -> None:
    assert previous_stage(BoxStage.SCAN) == BoxStage.PREPARATION
    assert previous_stage(BoxStage.COMPLETED) == BoxStage.QUALITY_CONTROL


# --- recording work ---


def test_recording_work_stamps_the_user_and_time() -> None:
    doc, user = make_doc(), make_user()
    before = datetime.now(UTC)

    set_stage_record(doc, BoxStage.SCAN, user)

    assert doc.scanned_by_id == user.id
    assert doc.scanned_at is not None
    assert doc.scanned_at >= before


def test_withdrawing_work_clears_the_stamp() -> None:
    doc, user = make_doc(), make_user()
    set_stage_record(doc, BoxStage.SCAN, user)

    set_stage_record(doc, BoxStage.SCAN, None)

    assert doc.scanned_at is None
    assert doc.scanned_by_id is None


def test_completed_stage_records_nothing() -> None:
    """There are no columns for `completed`, so this is a no-op, not an error."""
    doc = make_doc()

    set_stage_record(doc, BoxStage.COMPLETED, make_user())

    assert doc.prepared_at is None
    assert doc.scanned_at is None
    assert doc.checked_at is None


def test_clearing_a_stage_forgets_only_that_stage() -> None:
    doc, user = make_doc(), make_user()
    set_stage_record(doc, BoxStage.PREPARATION, user)
    set_stage_record(doc, BoxStage.SCAN, user)

    clear_stage_records(doc, BoxStage.SCAN)

    assert doc.prepared_at is not None
    assert doc.scanned_at is None


def test_clearing_the_completed_stage_is_a_no_op() -> None:
    doc, user = make_doc(), make_user()
    set_stage_record(doc, BoxStage.PREPARATION, user)

    clear_stage_records(doc, BoxStage.COMPLETED)

    assert doc.prepared_at is not None


def test_a_doc_counts_as_done_only_for_stages_it_has_records_for() -> None:
    doc, user = make_doc(), make_user()
    set_stage_record(doc, BoxStage.PREPARATION, user)

    assert doc_done_in_stage(doc, BoxStage.PREPARATION) is True
    assert doc_done_in_stage(doc, BoxStage.SCAN) is False


def test_every_doc_counts_as_done_once_the_box_is_completed() -> None:
    assert doc_done_in_stage(make_doc(), BoxStage.COMPLETED) is True


# --- finishing a stage ---


def test_an_empty_box_never_finishes_a_stage() -> None:
    """A box with no docs has nothing to do, but is not therefore done."""
    box = Box(name="empty", stage=BoxStage.PREPARATION)

    assert is_stage_finished(box) is False


def test_a_stage_is_finished_only_when_every_doc_is_done() -> None:
    user = make_user()
    box = Box(name="half", stage=BoxStage.PREPARATION)
    done, pending = make_doc(), make_doc()
    set_stage_record(done, BoxStage.PREPARATION, user)
    box.docs = [done, pending]

    assert is_stage_finished(box) is False
    assert stage_done_count(box) == 1

    set_stage_record(pending, BoxStage.PREPARATION, user)

    assert is_stage_finished(box) is True
    assert stage_done_count(box) == 2


def test_a_completed_box_counts_as_finished() -> None:
    assert is_stage_finished(Box(name="done", stage=BoxStage.COMPLETED)) is True


# --- advancing ---


def test_finishing_the_last_doc_advances_and_releases_the_box() -> None:
    user = make_user()
    box = Box(name="ready", stage=BoxStage.PREPARATION, assignee_id=user.id)
    doc = make_doc()
    set_stage_record(doc, BoxStage.PREPARATION, user)
    box.docs = [doc]

    assert advance_if_finished(box) is True
    assert box.stage == BoxStage.SCAN
    assert box.assignee_id is None


def test_a_box_with_outstanding_work_does_not_advance() -> None:
    box = Box(name="busy", stage=BoxStage.PREPARATION, assignee_id=uuid.uuid4())
    box.docs = [make_doc()]

    assert advance_if_finished(box) is False
    assert box.stage == BoxStage.PREPARATION
    assert box.assignee_id is not None


def test_a_completed_box_does_not_advance_further() -> None:
    box = Box(name="finished", stage=BoxStage.COMPLETED)

    assert advance_if_finished(box) is False
    assert box.stage == BoxStage.COMPLETED


def test_quality_control_advances_to_completed() -> None:
    user = make_user()
    box = Box(name="last-leg", stage=BoxStage.QUALITY_CONTROL)
    doc = make_doc()
    set_stage_record(doc, BoxStage.QUALITY_CONTROL, user)
    box.docs = [doc]

    assert advance_if_finished(box) is True
    assert box.stage == BoxStage.COMPLETED

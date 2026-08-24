"""
The rules of the digitisation pipeline.

Pure domain logic: no database session, no HTTP, no side effects. Everything
here answers questions about stages and about the work recorded against a
document, and is shared by the box and doc services.
"""

from datetime import UTC, datetime

from app.models import Box, BoxStage, Doc, User

# The pipeline, in order. A box moves forward one step at a time.
STAGE_ORDER: list[BoxStage] = [
    BoxStage.PREPARATION,
    BoxStage.SCAN,
    BoxStage.QUALITY_CONTROL,
    BoxStage.COMPLETED,
]

# Which pair of Doc columns records the work done in each stage.
STAGE_FIELDS: dict[BoxStage, tuple[str, str]] = {
    BoxStage.PREPARATION: ("prepared_at", "prepared_by_id"),
    BoxStage.SCAN: ("scanned_at", "scanned_by_id"),
    BoxStage.QUALITY_CONTROL: ("checked_at", "checked_by_id"),
}


def next_stage(stage: BoxStage) -> BoxStage | None:
    """The stage after this one, or None if the pipeline ends here."""
    index = STAGE_ORDER.index(stage)
    if index + 1 >= len(STAGE_ORDER):
        return None
    return STAGE_ORDER[index + 1]


def previous_stage(stage: BoxStage) -> BoxStage | None:
    """The stage before this one, or None if this is the first."""
    index = STAGE_ORDER.index(stage)
    if index == 0:
        return None
    return STAGE_ORDER[index - 1]


def doc_done_in_stage(doc: Doc, stage: BoxStage) -> bool:
    """Whether this doc has had the work of `stage` recorded against it."""
    fields = STAGE_FIELDS.get(stage)
    if fields is None:
        return True
    return getattr(doc, fields[0]) is not None


def clear_stage_records(doc: Doc, stage: BoxStage) -> None:
    """Forget the work recorded for `stage`, so it has to be done again."""
    fields = STAGE_FIELDS.get(stage)
    if fields is None:
        return
    setattr(doc, fields[0], None)
    setattr(doc, fields[1], None)


def set_stage_record(doc: Doc, stage: BoxStage, user: User | None) -> None:
    """
    Record, or withdraw, the work done on a doc for `stage`.

    Passing a user stamps the doc with them and the current time; passing
    None undoes that, for when someone unticks a doc by mistake.
    """
    fields = STAGE_FIELDS.get(stage)
    if fields is None:
        return
    at_field, by_field = fields
    if user is None:
        setattr(doc, at_field, None)
        setattr(doc, by_field, None)
    else:
        setattr(doc, at_field, datetime.now(UTC))
        setattr(doc, by_field, user.id)


def stage_done_count(box: Box) -> int:
    """How many of the box's docs are finished for its current stage."""
    return sum(1 for d in box.docs if doc_done_in_stage(d, box.stage))


def is_stage_finished(box: Box) -> bool:
    """A stage is finished when the box holds docs and all are done for it."""
    if box.stage == BoxStage.COMPLETED:
        return True
    return bool(box.docs) and all(doc_done_in_stage(d, box.stage) for d in box.docs)


def advance_if_finished(box: Box) -> bool:
    """
    Move the box on if every doc is done for its current stage, releasing
    it back to the pool.

    Mutates the box but does not persist it: the caller decides whether to
    save, and `False` means nothing changed. Keeping the transition here
    rather than in a service means the rule has one home, whether a box
    advances because its last doc was ticked off or for any other reason.
    """
    if box.stage == BoxStage.COMPLETED:
        return False
    if not is_stage_finished(box):
        return False
    upcoming = next_stage(box.stage)
    if upcoming is None:
        return False
    box.stage = upcoming
    box.assignee_id = None
    return True

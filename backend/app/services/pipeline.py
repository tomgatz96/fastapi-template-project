"""
The rules of the digitisation pipeline.

Pure domain logic: no database session, no HTTP, no side effects. Everything
here answers questions about stages and about the work recorded against a
document, and is shared by the box and doc services.
"""

from app.models import Box, BoxStage, Doc

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


def stage_done_count(box: Box) -> int:
    """How many of the box's docs are finished for its current stage."""
    return sum(1 for d in box.docs if doc_done_in_stage(d, box.stage))


def is_stage_finished(box: Box) -> bool:
    """A stage is finished when the box holds docs and all are done for it."""
    if box.stage == BoxStage.COMPLETED:
        return True
    return bool(box.docs) and all(doc_done_in_stage(d, box.stage) for d in box.docs)

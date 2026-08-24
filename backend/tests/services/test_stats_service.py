"""
Unit tests for the work report, using an in-memory repository.

`StatsService` depends on a repository rather than a `Session`, so the totals
can be checked against handmade records with no database, no migration and no
clock-dependent setup. The queries themselves — that the right columns are
read, and that the month cutoff is applied in SQL — stay covered by the API
tests in `tests/api/routes/test_stats.py`.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.models import BoxStage, User
from app.repositories.stats_repository import CompletedWork
from app.services.stats_service import (
    PeriodBoundaries,
    StatsService,
    empty_buckets,
    periods_covering,
    record,
)


class FakeStatsRepository:
    """An in-memory stand-in with the same surface the service uses."""

    def __init__(
        self, users: list[User], work: dict[BoxStage, list[CompletedWork]] | None = None
    ) -> None:
        self.users = users
        self.work = work or {}
        self.cutoffs: list[datetime] = []

    def list_users(self) -> list[User]:
        return self.users

    def completed_since(
        self, stage: BoxStage, since: datetime
    ) -> list[CompletedWork]:
        self.cutoffs.append(since)
        return [w for w in self.work.get(stage, []) if w.completed_at >= since]


def make_user(name: str | None = None) -> User:
    return User(
        email=f"{uuid.uuid4()}@example.com",
        hashed_password="x",
        full_name=name,
    )


def boundaries_now() -> PeriodBoundaries:
    """Boundaries far enough apart that a test can land between them."""
    now = datetime.now(UTC)
    return PeriodBoundaries(
        day=now - timedelta(hours=1),
        week=now - timedelta(days=3),
        month=now - timedelta(days=20),
    )


# --- which windows a moment falls into ---


def test_moment_today_counts_in_all_three_periods() -> None:
    bounds = boundaries_now()
    assert set(periods_covering(datetime.now(UTC), bounds)) == {"day", "week", "month"}


def test_moment_earlier_this_week_skips_today() -> None:
    bounds = boundaries_now()
    moment = bounds.day - timedelta(minutes=1)
    assert set(periods_covering(moment, bounds)) == {"week", "month"}


def test_moment_earlier_this_month_counts_only_in_month() -> None:
    bounds = boundaries_now()
    moment = bounds.week - timedelta(minutes=1)
    assert periods_covering(moment, bounds) == ["month"]


def test_moment_exactly_on_a_boundary_is_inside_it() -> None:
    """Boundaries are inclusive, so work at midnight counts as today's."""
    bounds = boundaries_now()
    assert "day" in periods_covering(bounds.day, bounds)


# --- bucket arithmetic ---


def test_empty_buckets_start_at_zero() -> None:
    buckets = empty_buckets()
    for period in ("day", "week", "month"):
        stats = getattr(buckets, period)
        assert stats.total.docs == 0
        assert stats.total.pages == 0
        assert stats.preparation.pages == 0


def test_record_adds_to_both_the_stage_and_the_total() -> None:
    buckets = empty_buckets()
    record(buckets, "day", BoxStage.SCAN, pages=12)

    assert buckets.day.scan.docs == 1
    assert buckets.day.scan.pages == 12
    assert buckets.day.total.docs == 1
    assert buckets.day.total.pages == 12
    # Other stages and periods are untouched.
    assert buckets.day.preparation.docs == 0
    assert buckets.week.total.docs == 0


def test_record_does_not_double_count_across_stages() -> None:
    buckets = empty_buckets()
    record(buckets, "month", BoxStage.PREPARATION, pages=3)
    record(buckets, "month", BoxStage.QUALITY_CONTROL, pages=4)

    assert buckets.month.total.docs == 2
    assert buckets.month.total.pages == 7
    assert buckets.month.scan.docs == 0


# --- the report ---


def test_report_lists_every_user_even_with_no_work() -> None:
    idle = make_user("Idle Person")
    service = StatsService(FakeStatsRepository([idle]))

    report = service.report(tz_offset_minutes=0)

    assert [u.user_id for u in report.users] == [idle.id]
    assert report.users[0].stats.month.total.docs == 0
    assert report.totals.month.total.docs == 0


def test_report_credits_work_to_the_user_who_did_it() -> None:
    worker = make_user("Worker")
    bystander = make_user("Bystander")
    now = datetime.now(UTC)

    repo = FakeStatsRepository(
        [worker, bystander],
        {BoxStage.PREPARATION: [CompletedWork(worker.id, now, pages=5)]},
    )
    report = StatsService(repo).report(tz_offset_minutes=0)

    by_id = {u.user_id: u for u in report.users}
    assert by_id[worker.id].stats.day.preparation.pages == 5
    assert by_id[bystander.id].stats.day.preparation.pages == 0
    assert report.totals.day.preparation.pages == 5


def test_report_counts_unattributed_work_in_the_totals_only() -> None:
    """A doc whose user was deleted still happened, so the totals keep it."""
    worker = make_user("Worker")
    now = datetime.now(UTC)

    repo = FakeStatsRepository(
        [worker],
        {BoxStage.SCAN: [CompletedWork(None, now, pages=9)]},
    )
    report = StatsService(repo).report(tz_offset_minutes=0)

    assert report.totals.day.scan.pages == 9
    assert report.users[0].stats.day.scan.pages == 0


def test_report_counts_one_doc_in_every_period_it_falls_inside() -> None:
    worker = make_user("Worker")
    now = datetime.now(UTC)

    repo = FakeStatsRepository(
        [worker],
        {BoxStage.QUALITY_CONTROL: [CompletedWork(worker.id, now, pages=2)]},
    )
    report = StatsService(repo).report(tz_offset_minutes=0)

    stats = report.users[0].stats
    assert stats.day.quality_control.docs == 1
    assert stats.week.quality_control.docs == 1
    assert stats.month.quality_control.docs == 1


def test_report_sums_pages_across_stages_into_the_total() -> None:
    worker = make_user("Worker")
    now = datetime.now(UTC)

    repo = FakeStatsRepository(
        [worker],
        {
            BoxStage.PREPARATION: [CompletedWork(worker.id, now, pages=1)],
            BoxStage.SCAN: [CompletedWork(worker.id, now, pages=2)],
            BoxStage.QUALITY_CONTROL: [CompletedWork(worker.id, now, pages=4)],
        },
    )
    report = StatsService(repo).report(tz_offset_minutes=0)

    assert report.totals.day.total.docs == 3
    assert report.totals.day.total.pages == 7


def test_report_reads_only_back_to_the_month_boundary() -> None:
    """The widest window is a month, so nothing older is ever fetched."""
    repo = FakeStatsRepository([make_user("Worker")])
    report = StatsService(repo).report(tz_offset_minutes=0)

    assert repo.cutoffs, "expected the service to query the repository"
    assert all(cutoff == report.month_start for cutoff in repo.cutoffs)


def test_report_orders_users_by_name_ignoring_capitalisation() -> None:
    users = [make_user("zoe"), make_user("Adam"), make_user("bella")]
    report = StatsService(FakeStatsRepository(users)).report(tz_offset_minutes=0)

    assert [u.user_name for u in report.users] == ["Adam", "bella", "zoe"]


def test_report_falls_back_to_email_when_a_user_has_no_name() -> None:
    nameless = make_user(None)
    report = StatsService(FakeStatsRepository([nameless])).report(tz_offset_minutes=0)

    assert report.users[0].user_name == nameless.email

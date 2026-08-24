"""
The work report.

Turns raw records of completed work into the day/week/month totals the stats
page shows, broken down by stage and by user. Where the period boundaries fall
is decided here too: "today" is a domain question, because it depends on the
viewer's clock rather than on anything in the database.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from app.models import (
    BoxStage,
    PeriodStats,
    StageStats,
    StatsBuckets,
    StatsPublic,
    User,
    UserStats,
)
from app.repositories.stats_repository import StatsRepository
from app.services.pipeline import STAGE_FIELDS

# The three windows the report covers, widest last.
PERIODS = ("day", "week", "month")


class PeriodBoundaries(NamedTuple):
    """When today, this week and this month began, in UTC."""

    day: datetime
    week: datetime
    month: datetime


def period_starts(tz_offset_minutes: int) -> PeriodBoundaries:
    """
    Work out when today, this week and this month began, in UTC.

    Timestamps are stored in UTC but people think in local time, so the
    boundaries are found in the caller's local time and converted back.
    `tz_offset_minutes` follows the JavaScript convention: minutes behind
    UTC, so UTC+3 is -180.
    """
    offset = timedelta(minutes=tz_offset_minutes)
    now_local = datetime.now(UTC) - offset

    day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    week_local = day_local - timedelta(days=day_local.weekday())  # Monday
    month_local = day_local.replace(day=1)

    return PeriodBoundaries(
        day=day_local + offset,
        week=week_local + offset,
        month=month_local + offset,
    )


class StatsService:
    def __init__(self, stats: StatsRepository) -> None:
        self.stats = stats

    def report(self, tz_offset_minutes: int) -> StatsPublic:
        """
        Docs and pages completed today, this week and this month, per stage,
        both overall and per user.

        Only a month's worth of records is read, since that is the widest
        window on the page; the narrower ones are counted from the same rows
        rather than queried again.
        """
        boundaries = period_starts(tz_offset_minutes)

        users = self.stats.list_users()
        per_user: dict[uuid.UUID, StatsBuckets] = {u.id: empty_buckets() for u in users}
        totals = empty_buckets()

        for stage in STAGE_FIELDS:
            for work in self.stats.completed_since(stage, boundaries.month):
                own_buckets = (
                    per_user.get(work.user_id) if work.user_id is not None else None
                )
                for period in periods_covering(work.completed_at, boundaries):
                    record(totals, period, stage, work.pages)
                    if own_buckets is not None:
                        record(own_buckets, period, stage, work.pages)

        return StatsPublic(
            day_start=boundaries.day,
            week_start=boundaries.week,
            month_start=boundaries.month,
            totals=totals,
            users=self._user_stats(users, per_user),
        )

    # --- internals ---

    @staticmethod
    def _user_stats(
        users: Sequence[User], per_user: dict[uuid.UUID, StatsBuckets]
    ) -> list[UserStats]:
        """One entry per user, ordered by name so the table reads predictably."""
        entries = [
            UserStats(
                user_id=user.id,
                user_name=user.full_name or user.email,
                stats=per_user[user.id],
            )
            for user in users
        ]
        return sorted(entries, key=lambda entry: entry.user_name.lower())


# --- bucket arithmetic ---
#
# Pure functions over the report's own shapes: no repository, no request. They
# are module level rather than methods because nothing about them depends on
# where the numbers came from.


def empty_period() -> PeriodStats:
    """A single period with every stage at zero."""
    return PeriodStats(
        preparation=StageStats(),
        scan=StageStats(),
        quality_control=StageStats(),
        total=StageStats(),
    )


def empty_buckets() -> StatsBuckets:
    """A full set of day/week/month periods, all at zero."""
    return StatsBuckets(day=empty_period(), week=empty_period(), month=empty_period())


def periods_covering(moment: datetime, boundaries: PeriodBoundaries) -> list[str]:
    """
    Which of the three windows this moment falls inside.

    The windows nest, so anything in today is also in this week and this
    month, and is counted once in each.
    """
    periods = ["month"]
    if moment >= boundaries.week:
        periods.append("week")
    if moment >= boundaries.day:
        periods.append("day")
    return periods


def record(buckets: StatsBuckets, period: str, stage: BoxStage, pages: int) -> None:
    """Count one finished doc against a period, in its stage and in the total."""
    period_stats: PeriodStats = getattr(buckets, period)
    for target in (getattr(period_stats, stage.value), period_stats.total):
        target.docs += 1
        target.pages += pages

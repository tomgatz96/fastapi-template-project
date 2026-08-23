import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Doc,
    PeriodStats,
    StageStats,
    StatsBuckets,
    StatsPublic,
    User,
    UserStats,
)

router = APIRouter(prefix="/stats", tags=["stats"])

# Each stage, and the pair of Doc columns recording work done in it.
STAGE_COLUMNS: list[tuple[str, Any, Any]] = [
    ("preparation", Doc.prepared_at, Doc.prepared_by_id),
    ("scan", Doc.scanned_at, Doc.scanned_by_id),
    ("quality_control", Doc.checked_at, Doc.checked_by_id),
]


def period_starts(tz_offset_minutes: int) -> tuple[datetime, datetime, datetime]:
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

    return (day_local + offset, week_local + offset, month_local + offset)


def _empty_buckets() -> StatsBuckets:
    return StatsBuckets(
        day=PeriodStats(
            preparation=StageStats(),
            scan=StageStats(),
            quality_control=StageStats(),
            total=StageStats(),
        ),
        week=PeriodStats(
            preparation=StageStats(),
            scan=StageStats(),
            quality_control=StageStats(),
            total=StageStats(),
        ),
        month=PeriodStats(
            preparation=StageStats(),
            scan=StageStats(),
            quality_control=StageStats(),
            total=StageStats(),
        ),
    )


def _add(buckets: StatsBuckets, period: str, stage: str, pages: int) -> None:
    period_stats: PeriodStats = getattr(buckets, period)
    for target in (getattr(period_stats, stage), period_stats.total):
        target.docs += 1
        target.pages += pages


@router.get("/", response_model=StatsPublic)
def read_stats(
    session: SessionDep,
    current_user: CurrentUser,
    tz_offset_minutes: int = Query(
        default=0,
        ge=-1440,
        le=1440,
        description="Minutes behind UTC, as returned by JavaScript's getTimezoneOffset().",
    ),
) -> Any:
    """
    Docs and pages completed today, this week and this month, broken down
    by stage, both overall and per user.
    """
    day_start, week_start, month_start = period_starts(tz_offset_minutes)

    users = session.exec(select(User)).all()
    per_user: dict[uuid.UUID, StatsBuckets] = {u.id: _empty_buckets() for u in users}
    totals = _empty_buckets()

    for stage, at_column, by_column in STAGE_COLUMNS:
        rows = session.exec(
            select(by_column, at_column, Doc.pages).where(at_column >= month_start)
        ).all()

        for user_id, completed_at, pages in rows:
            pages = pages or 0

            periods = ["month"]
            if completed_at >= week_start:
                periods.append("week")
            if completed_at >= day_start:
                periods.append("day")

            for period in periods:
                _add(totals, period, stage, pages)
                if user_id is not None and user_id in per_user:
                    _add(per_user[user_id], period, stage, pages)

    user_stats = [
        UserStats(
            user_id=u.id,
            user_name=u.full_name or u.email,
            stats=per_user[u.id],
        )
        for u in users
    ]
    user_stats.sort(key=lambda u: u.user_name.lower())

    return StatsPublic(
        day_start=day_start,
        week_start=week_start,
        month_start=month_start,
        totals=totals,
        users=user_stats,
    )

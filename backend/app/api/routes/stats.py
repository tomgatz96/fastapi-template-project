"""
HTTP endpoint for the work report.

The controller binds the route, validates the one query parameter and hands
straight over to `app/services/stats_service.py`, which decides what "today"
means and assembles the totals.
"""

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, StatsServiceDep
from app.models import StatsPublic

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsPublic)
def read_stats(
    service: StatsServiceDep,
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
    return service.report(tz_offset_minutes)

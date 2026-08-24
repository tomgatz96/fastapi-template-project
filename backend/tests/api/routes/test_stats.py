"""Docs and pages completed today, this week and this month."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes.stats import period_starts
from app.core.config import settings
from app.models import Box, Doc
from tests.utils.box import create_random_box
from tests.utils.utils import random_lower_string


@pytest.fixture(autouse=True)
def release_all_claims(db: Session):
    yield
    db.expire_all()
    for box in db.exec(select(Box).where(Box.assignee_id.is_not(None))).all():
        box.assignee_id = None
        db.add(box)
    db.commit()


def _get_stats(client: TestClient, headers: dict[str, str], tz: int = 0):
    response = client.get(
        f"{settings.API_V1_STR}/stats/?tz_offset_minutes={tz}", headers=headers
    )
    assert response.status_code == 200
    return response.json()


def _find_user(stats: dict, name: str) -> dict | None:
    return next((u for u in stats["users"] if u["user_name"] == name), None)


def _prepare_doc(
    client: TestClient, headers: dict[str, str], db: Session, pages: int
) -> str:
    """Claim a fresh box, add one doc, mark it prepared. Returns the doc id."""
    box = create_random_box(db)
    created = client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=headers,
        json={"name": random_lower_string(), "description": "d", "pages": pages},
    )
    assert created.status_code == 200
    doc_id = created.json()["id"]

    assert (
        client.post(
            f"{settings.API_V1_STR}/boxes/{box.id}/claim", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"{settings.API_V1_STR}/docs/{doc_id}",
            headers=headers,
            json={"completed": True},
        ).status_code
        == 200
    )
    return doc_id


# --- Period boundaries ---


def test_week_starts_on_monday() -> None:
    _, week_start, _ = period_starts(0)
    assert week_start.weekday() == 0


def test_month_starts_on_the_first() -> None:
    _, _, month_start = period_starts(0)
    assert month_start.day == 1


def test_boundaries_shift_with_timezone() -> None:
    """
    UTC+3 means the local day began three hours earlier in UTC terms.

    Measured modulo a day, because once Athens has crossed midnight and UTC
    has not, its day start is three hours earlier on the *next* date, and a
    plain subtraction would read as minus twenty-one hours.
    """
    utc_day, _, _ = period_starts(0)
    athens_day, _, _ = period_starts(-180)
    assert (utc_day - athens_day) % timedelta(days=1) == timedelta(hours=3)


def test_day_start_is_not_after_week_start_or_month_start() -> None:
    day, week, month = period_starts(0)
    assert week <= day
    assert month <= day


# --- Totals ---


def test_stats_endpoint_returns_every_period(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    stats = _get_stats(client, superuser_token_headers)
    for period in ("day", "week", "month"):
        assert period in stats["totals"]
        for stage in ("preparation", "scan", "quality_control", "total"):
            assert "docs" in stats["totals"][period][stage]
            assert "pages" in stats["totals"][period][stage]


def test_completing_a_doc_counts_towards_preparation(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    before = _get_stats(client, superuser_token_headers)["totals"]["day"]["preparation"]
    _prepare_doc(client, superuser_token_headers, db, pages=7)
    after = _get_stats(client, superuser_token_headers)["totals"]["day"]["preparation"]

    assert after["docs"] == before["docs"] + 1
    assert after["pages"] == before["pages"] + 7


def test_work_counts_in_every_period_that_contains_it(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Something done today is also inside this week and this month."""
    before = _get_stats(client, superuser_token_headers)["totals"]
    _prepare_doc(client, superuser_token_headers, db, pages=5)
    after = _get_stats(client, superuser_token_headers)["totals"]

    for period in ("day", "week", "month"):
        assert (
            after[period]["preparation"]["docs"]
            == before[period]["preparation"]["docs"] + 1
        )


def test_total_is_the_sum_of_the_stages(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    _prepare_doc(client, superuser_token_headers, db, pages=11)
    month = _get_stats(client, superuser_token_headers)["totals"]["month"]

    assert month["total"]["docs"] == (
        month["preparation"]["docs"] + month["scan"]["docs"] + month["quality_control"]["docs"]
    )
    assert month["total"]["pages"] == (
        month["preparation"]["pages"] + month["scan"]["pages"] + month["quality_control"]["pages"]
    )


def test_old_work_is_excluded(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Work from before this month must not appear in any bucket."""
    doc_id = _prepare_doc(client, superuser_token_headers, db, pages=9)
    before = _get_stats(client, superuser_token_headers)["totals"]["month"]["preparation"]

    doc = db.get(Doc, doc_id)
    assert doc is not None
    doc.prepared_at = datetime.now(UTC) - timedelta(days=120)
    db.add(doc)
    db.commit()

    after = _get_stats(client, superuser_token_headers)["totals"]["month"]["preparation"]
    assert after["docs"] == before["docs"] - 1
    assert after["pages"] == before["pages"] - 9


# --- Per user ---


def test_every_user_appears_even_with_no_work(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_box(db)  # creates a fresh user as owner
    stats = _get_stats(client, superuser_token_headers)
    assert len(stats["users"]) >= 2
    assert all("stats" in u for u in stats["users"])


def test_work_is_attributed_to_the_user_who_did_it(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    me = client.get(
        f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers
    ).json()
    name = me["full_name"] or me["email"]

    before = _find_user(_get_stats(client, superuser_token_headers), name)
    assert before is not None
    before_docs = before["stats"]["day"]["preparation"]["docs"]

    _prepare_doc(client, normal_user_token_headers, db, pages=4)

    after = _find_user(_get_stats(client, superuser_token_headers), name)
    assert after is not None
    assert after["stats"]["day"]["preparation"]["docs"] == before_docs + 1
    assert after["stats"]["day"]["preparation"]["pages"] >= 4


def test_users_are_sorted_by_name(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    stats = _get_stats(client, superuser_token_headers)
    names = [u["user_name"].lower() for u in stats["users"]]
    assert names == sorted(names)


def test_stats_require_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/stats/")
    assert response.status_code == 401

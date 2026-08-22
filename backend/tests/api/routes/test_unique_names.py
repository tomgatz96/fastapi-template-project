"""Box and doc names are unique across the app, ignoring capitalisation."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Box
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


def _create_box(client: TestClient, headers: dict[str, str], name: str):
    return client.post(
        f"{settings.API_V1_STR}/boxes/",
        headers=headers,
        json={"name": name, "description": "d"},
    )


def _create_doc(client: TestClient, headers: dict[str, str], box_id: str, name: str):
    return client.post(
        f"{settings.API_V1_STR}/boxes/{box_id}/docs/",
        headers=headers,
        json={"name": name, "description": "d", "pages": 1},
    )


# --- Boxes ---


def test_duplicate_box_name_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = random_lower_string()
    assert _create_box(client, superuser_token_headers, name).status_code == 200

    response = _create_box(client, superuser_token_headers, name)
    assert response.status_code == 409
    assert response.json()["detail"] == "A box with this name already exists"


def test_box_name_check_ignores_capitalisation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = random_lower_string()
    assert _create_box(client, superuser_token_headers, name).status_code == 200

    response = _create_box(client, superuser_token_headers, name.upper())
    assert response.status_code == 409


def test_box_name_check_ignores_surrounding_spaces(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = random_lower_string()
    assert _create_box(client, superuser_token_headers, name).status_code == 200

    response = _create_box(client, superuser_token_headers, f"  {name}  ")
    assert response.status_code == 409


def test_box_name_is_stored_trimmed(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = random_lower_string()
    response = _create_box(client, superuser_token_headers, f"  {name}  ")
    assert response.status_code == 200
    assert response.json()["name"] == name


def test_renaming_a_box_to_an_existing_name_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    first = random_lower_string()
    second = random_lower_string()
    assert _create_box(client, superuser_token_headers, first).status_code == 200
    created = _create_box(client, superuser_token_headers, second)
    assert created.status_code == 200

    response = client.put(
        f"{settings.API_V1_STR}/boxes/{created.json()['id']}",
        headers=superuser_token_headers,
        json={"name": first.upper()},
    )
    assert response.status_code == 409


def test_renaming_a_box_to_its_own_name_is_allowed(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Editing a box without changing its name must not trip the check."""
    name = random_lower_string()
    created = _create_box(client, superuser_token_headers, name)
    assert created.status_code == 200

    response = client.put(
        f"{settings.API_V1_STR}/boxes/{created.json()['id']}",
        headers=superuser_token_headers,
        json={"name": name, "description": "changed"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "changed"


# --- Docs ---


def test_duplicate_doc_name_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    name = random_lower_string()
    assert _create_doc(client, superuser_token_headers, str(box.id), name).status_code == 200

    response = _create_doc(client, superuser_token_headers, str(box.id), name)
    assert response.status_code == 409
    assert response.json()["detail"] == "A doc with this name already exists"


def test_duplicate_doc_name_is_rejected_across_boxes(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Doc names are unique app-wide, not just within their own box."""
    first_box = create_random_box(db)
    second_box = create_random_box(db)
    name = random_lower_string()
    assert (
        _create_doc(client, superuser_token_headers, str(first_box.id), name).status_code
        == 200
    )

    response = _create_doc(client, superuser_token_headers, str(second_box.id), name)
    assert response.status_code == 409


def test_doc_name_check_ignores_capitalisation(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    name = random_lower_string()
    assert _create_doc(client, superuser_token_headers, str(box.id), name).status_code == 200

    response = _create_doc(client, superuser_token_headers, str(box.id), name.upper())
    assert response.status_code == 409


def test_renaming_a_doc_to_an_existing_name_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    first = random_lower_string()
    second = random_lower_string()
    assert _create_doc(client, superuser_token_headers, str(box.id), first).status_code == 200
    created = _create_doc(client, superuser_token_headers, str(box.id), second)
    assert created.status_code == 200

    response = client.put(
        f"{settings.API_V1_STR}/docs/{created.json()['id']}",
        headers=superuser_token_headers,
        json={"name": first},
    )
    assert response.status_code == 409


def test_renaming_a_doc_to_its_own_name_is_allowed(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    name = random_lower_string()
    created = _create_doc(client, superuser_token_headers, str(box.id), name)
    assert created.status_code == 200

    response = client.put(
        f"{settings.API_V1_STR}/docs/{created.json()['id']}",
        headers=superuser_token_headers,
        json={"name": name, "pages": 42},
    )
    assert response.status_code == 200
    assert response.json()["pages"] == 42


# --- Searching by name ---


def test_search_finds_boxes_by_partial_name(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    unique = random_lower_string()
    name = f"invoice-{unique}"
    assert _create_box(client, superuser_token_headers, name).status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/boxes/?q={unique[:8]}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    names = [b["name"] for b in response.json()["data"]]
    assert name in names


def test_search_ignores_capitalisation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = random_lower_string()
    assert _create_box(client, superuser_token_headers, name).status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/boxes/?q={name.upper()}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert name in [b["name"] for b in response.json()["data"]]


def test_search_with_no_matches_returns_nothing(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/boxes/?q=zzz-nothing-matches-this-zzz",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["data"] == []


def test_search_can_be_combined_with_stage(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = random_lower_string()
    assert _create_box(client, superuser_token_headers, name).status_code == 200

    in_prep = client.get(
        f"{settings.API_V1_STR}/boxes/?q={name}&stage=preparation",
        headers=superuser_token_headers,
    ).json()
    in_completed = client.get(
        f"{settings.API_V1_STR}/boxes/?q={name}&stage=completed",
        headers=superuser_token_headers,
    ).json()

    assert in_prep["count"] == 1
    assert in_completed["count"] == 0

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Box
from tests.utils.box import create_random_box


@pytest.fixture(autouse=True)
def release_all_claims(db: Session):
    """
    A user may hold only one box, so a claim left behind by one test would
    break the next one. Clear every claim after each test.
    """
    yield
    db.expire_all()
    for box in db.exec(select(Box).where(Box.assignee_id.is_not(None))).all():
        box.assignee_id = None
        db.add(box)
    db.commit()


def _claim(client: TestClient, headers: dict[str, str], box_id: str):
    return client.post(f"{settings.API_V1_STR}/boxes/{box_id}/claim", headers=headers)


def _unclaim(client: TestClient, headers: dict[str, str], box_id: str):
    return client.post(f"{settings.API_V1_STR}/boxes/{box_id}/unclaim", headers=headers)


def _add_doc(
    client: TestClient, headers: dict[str, str], box_id: str, **kwargs
) -> dict:
    payload = {"name": "Doc", "description": "d", "pages": 1}
    payload.update(kwargs)
    r = client.post(
        f"{settings.API_V1_STR}/boxes/{box_id}/docs/", headers=headers, json=payload
    )
    assert r.status_code == 200
    return r.json()


# --- CRUD ---


def test_create_box(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Foo", "description": "Fighters"}
    response = client.post(
        f"{settings.API_V1_STR}/boxes/", headers=superuser_token_headers, json=data
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert content["owner_name"] is not None
    assert content["assignee_id"] is None
    assert content["assignee_name"] is None
    assert content["doc_count"] == 0
    assert content["total_pages"] == 0
    assert content["completed"] is False


def test_read_box(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(box.id)
    assert content["assignee_id"] is None


def test_read_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Box not found"


def test_read_box_is_shared_with_other_users(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(box.id)


def test_read_boxes(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_box(db)
    create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 2


def test_read_boxes_shows_boxes_owned_by_others(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    assert str(box.id) in [b["id"] for b in response.json()["data"]]


def test_update_box(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["name"] == data["name"]


def test_update_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"name": "x"},
    )
    assert response.status_code == 404


def test_update_box_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.put(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=normal_user_token_headers,
        json={"name": "x"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_delete_box(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Box deleted successfully"


def test_delete_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404


def test_delete_box_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 403


def test_delete_own_box_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/boxes/",
        headers=normal_user_token_headers,
        json={"name": "Mine", "description": "owned by the normal user"},
    )
    assert created.status_code == 200
    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{created.json()['id']}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


# --- Derived fields ---


def test_box_completed_false_when_empty(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    content = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    ).json()
    assert content["doc_count"] == 0
    assert content["total_pages"] == 0
    assert content["completed"] is False


def test_box_total_pages_sums_docs(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    for pages in (3, 12, 40):
        _add_doc(client, superuser_token_headers, str(box.id), pages=pages)
    content = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    ).json()
    assert content["doc_count"] == 3
    assert content["total_pages"] == 55
    assert content["completed"] is False


# --- Claiming ---


def test_claim_box_assigns_to_caller(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = _claim(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 200
    content = response.json()
    assert content["assignee_id"] is not None
    assert content["assignee_name"] is not None


def test_claim_box_twice_by_same_user_is_ok(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    first = _claim(client, normal_user_token_headers, str(box.id))
    second = _claim(client, normal_user_token_headers, str(box.id))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["assignee_id"] == second.json()["assignee_id"]


def test_claim_box_already_claimed_by_someone_else(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    box = create_random_box(db)
    assert _claim(client, superuser_token_headers, str(box.id)).status_code == 200
    response = _claim(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 409
    assert response.json()["detail"] == "This box is already claimed by another user"


def test_claim_second_box_is_rejected(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """A user may hold only one box at a time."""
    first_box = create_random_box(db)
    second_box = create_random_box(db)
    assert _claim(client, normal_user_token_headers, str(first_box.id)).status_code == 200

    response = _claim(client, normal_user_token_headers, str(second_box.id))
    assert response.status_code == 409
    assert "already have a box claimed" in response.json()["detail"]


def test_claim_second_box_after_releasing_first(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    first_box = create_random_box(db)
    second_box = create_random_box(db)
    assert _claim(client, normal_user_token_headers, str(first_box.id)).status_code == 200
    assert _unclaim(client, normal_user_token_headers, str(first_box.id)).status_code == 200
    assert _claim(client, normal_user_token_headers, str(second_box.id)).status_code == 200


def test_claim_completed_box_is_rejected(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    box = create_random_box(db)
    _add_doc(client, superuser_token_headers, str(box.id))
    assert _claim(client, superuser_token_headers, str(box.id)).status_code == 200
    docs = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/", headers=superuser_token_headers
    ).json()["data"]
    client.put(
        f"{settings.API_V1_STR}/docs/{docs[0]['id']}",
        headers=superuser_token_headers,
        json={"completed": True},
    )

    response = _claim(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 409
    assert response.json()["detail"] == "This box is already completed"


def test_claim_box_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = _claim(client, normal_user_token_headers, str(uuid.uuid4()))
    assert response.status_code == 404


def test_unclaim_box_by_assignee(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    response = _unclaim(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


def test_unclaim_box_that_is_not_claimed(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = _unclaim(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 409
    assert response.json()["detail"] == "This box is not claimed"


def test_unclaim_box_claimed_by_someone_else(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    box = create_random_box(db)
    assert _claim(client, superuser_token_headers, str(box.id)).status_code == 200
    response = _unclaim(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 403
    assert response.json()["detail"] == "You can only release a box assigned to you"


def test_superuser_can_unclaim_any_box(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    box = create_random_box(db)
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    response = _unclaim(client, superuser_token_headers, str(box.id))
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


# --- Auto-release ---


def test_box_is_released_when_last_doc_completed(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc_a = _add_doc(client, normal_user_token_headers, str(box.id), name="A")
    doc_b = _add_doc(client, normal_user_token_headers, str(box.id), name="B")
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200

    client.put(
        f"{settings.API_V1_STR}/docs/{doc_a['id']}",
        headers=normal_user_token_headers,
        json={"completed": True},
    )
    still_held = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=normal_user_token_headers
    ).json()
    assert still_held["assignee_id"] is not None
    assert still_held["completed"] is False

    client.put(
        f"{settings.API_V1_STR}/docs/{doc_b['id']}",
        headers=normal_user_token_headers,
        json={"completed": True},
    )
    released = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=normal_user_token_headers
    ).json()
    assert released["completed"] is True
    assert released["assignee_id"] is None
    assert released["assignee_name"] is None


def test_releasing_box_frees_user_to_claim_another(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Auto-release must also free the one-box-per-user slot."""
    box = create_random_box(db)
    other = create_random_box(db)
    doc = _add_doc(client, normal_user_token_headers, str(box.id))
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    client.put(
        f"{settings.API_V1_STR}/docs/{doc['id']}",
        headers=normal_user_token_headers,
        json={"completed": True},
    )
    assert _claim(client, normal_user_token_headers, str(other.id)).status_code == 200

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.box import create_random_box


def test_create_box(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Foo", "description": "Fighters"}
    response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert "owner_id" in content
    assert content["owner_name"] is not None
    assert content["doc_count"] == 0
    assert content["completed"] is False
    assert content["total_pages"] == 0


def test_read_box(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == box.name
    assert content["description"] == box.description
    assert content["id"] == str(box.id)
    assert content["owner_id"] == str(box.owner_id)
    assert content["doc_count"] == 0
    assert content["completed"] is False
    assert content["total_pages"] == 0


def test_read_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Box not found"


def test_read_box_is_shared_with_other_users(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Boxes are shared: a user who does not own the box can still read it."""
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(box.id)
    assert content["owner_id"] == str(box.owner_id)


def test_read_boxes(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_box(db)
    create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 2


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
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["id"] == str(box.id)


def test_update_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Box not found"


def test_update_box_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_delete_box(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Box deleted successfully"


def test_delete_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Box not found"


def test_delete_box_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_delete_own_box_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Even the owner cannot delete a box: deletion is superuser-only."""
    created = client.post(
        f"{settings.API_V1_STR}/boxes/",
        headers=normal_user_token_headers,
        json={"name": "Mine", "description": "owned by the normal user"},
    )
    assert created.status_code == 200
    box_id = created.json()["id"]

    response = client.delete(
        f"{settings.API_V1_STR}/boxes/{box_id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_read_boxes_shows_boxes_owned_by_others(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """The list endpoint is shared, so other people's boxes appear too."""
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    ids = [b["id"] for b in response.json()["data"]]
    assert str(box.id) in ids


# --- Box-specific business logic: doc_count / total_pages / completed ---


def test_box_completed_false_when_empty(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    content = response.json()
    assert content["doc_count"] == 0
    assert content["total_pages"] == 0
    assert content["completed"] is False


def test_box_completed_true_when_all_docs_done(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    for _ in range(3):
        client.post(
            f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
            headers=superuser_token_headers,
            json={"name": "Doc", "description": "d", "completed": True, "pages": 10},
        )
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    content = response.json()
    assert content["doc_count"] == 3
    assert content["total_pages"] == 30
    assert content["completed"] is True


def test_box_completed_false_when_one_doc_pending(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=superuser_token_headers,
        json={"name": "Doc 1", "description": "d", "completed": True, "pages": 5},
    )
    client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=superuser_token_headers,
        json={"name": "Doc 2", "description": "d", "completed": False, "pages": 7},
    )
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    content = response.json()
    assert content["doc_count"] == 2
    assert content["total_pages"] == 12
    assert content["completed"] is False


def test_box_total_pages_sums_docs(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    for pages in (3, 12, 40):
        client.post(
            f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
            headers=superuser_token_headers,
            json={"name": "Doc", "description": "d", "pages": pages},
        )
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    content = response.json()
    assert content["doc_count"] == 3
    assert content["total_pages"] == 55
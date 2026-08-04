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
    assert content["doc_count"] == 0
    assert content["completed"] is False


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


def test_read_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Box not found"


def test_read_box_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


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


# --- Box-specific business logic: doc_count / completed ---


def test_box_completed_false_when_empty(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    content = response.json()
    assert content["doc_count"] == 0
    assert content["completed"] is False


def test_box_completed_true_when_all_docs_done(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    for _ in range(3):
        client.post(
            f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
            headers=superuser_token_headers,
            json={"name": "Doc", "description": "d", "completed": True},
        )
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    content = response.json()
    assert content["doc_count"] == 3
    assert content["completed"] is True


def test_box_completed_false_when_one_doc_pending(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=superuser_token_headers,
        json={"name": "Doc 1", "description": "d", "completed": True},
    )
    client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=superuser_token_headers,
        json={"name": "Doc 2", "description": "d", "completed": False},
    )
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}", headers=superuser_token_headers
    )
    content = response.json()
    assert content["doc_count"] == 2
    assert content["completed"] is False
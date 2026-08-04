import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.box import create_random_box
from tests.utils.doc import create_random_doc


def test_create_doc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    data = {"name": "Foo", "description": "Fighters", "completed": False}
    response = client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["completed"] is False
    assert content["box_id"] == str(box.id)
    assert "id" in content


def test_create_doc_box_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    data = {"name": "Foo", "description": "Fighters", "completed": False}
    response = client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_read_doc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.get(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == doc.name
    assert content["description"] == doc.description
    assert content["id"] == str(doc.id)
    assert content["box_id"] == str(doc.box_id)


def test_read_doc_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/docs/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Doc not found"


def test_read_doc_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.get(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_read_docs(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    create_random_doc(db, box_id=box.id)
    create_random_doc(db, box_id=box.id)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 2


def test_read_docs_box_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{uuid.uuid4()}/docs/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Box not found"


def test_update_doc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    data = {"name": "Updated", "description": "Updated desc", "completed": True}
    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["completed"] is True


def test_update_doc_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Updated", "description": "Updated desc", "completed": True}
    response = client.put(
        f"{settings.API_V1_STR}/docs/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Doc not found"


def test_update_doc_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    data = {"name": "Updated", "description": "Updated desc", "completed": True}
    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_delete_doc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.delete(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Doc deleted successfully"


def test_delete_doc_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/docs/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Doc not found"


def test_delete_doc_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.delete(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
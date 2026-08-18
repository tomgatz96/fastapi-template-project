import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Box
from tests.utils.box import create_random_box
from tests.utils.doc import create_random_doc


@pytest.fixture(autouse=True)
def release_all_claims(db: Session):
    """A user may hold only one box; clear claims so tests stay independent."""
    yield
    db.expire_all()
    for box in db.exec(select(Box).where(Box.assignee_id.is_not(None))).all():
        box.assignee_id = None
        db.add(box)
    db.commit()


def _claim(client: TestClient, headers: dict[str, str], box_id: str):
    return client.post(f"{settings.API_V1_STR}/boxes/{box_id}/claim", headers=headers)


def _complete(client: TestClient, headers: dict[str, str], doc_id: str, value=True):
    return client.put(
        f"{settings.API_V1_STR}/docs/{doc_id}",
        headers=headers,
        json={"completed": value},
    )


# --- CRUD ---


def test_create_doc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    data = {"name": "Foo", "description": "Fighters", "pages": 25}
    response = client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["pages"] == 25
    assert content["completed"] is False
    assert content["box_id"] == str(box.id)
    assert content["prepared_at"] is None
    assert content["prepared_by_name"] is None
    assert content["scanned_at"] is None
    assert content["checked_at"] is None


def test_create_doc_in_unclaimed_box_by_any_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """An unclaimed box is open for anyone to set up."""
    box = create_random_box(db)
    response = client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=normal_user_token_headers,
        json={"name": "Foo", "description": "d", "pages": 3},
    )
    assert response.status_code == 200


def test_create_doc_in_box_claimed_by_someone_else(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    box = create_random_box(db)
    assert _claim(client, superuser_token_headers, str(box.id)).status_code == 200
    response = client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=normal_user_token_headers,
        json={"name": "Foo", "description": "d", "pages": 3},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "This box is claimed by another user"


def test_read_doc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.get(
        f"{settings.API_V1_STR}/docs/{doc.id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(doc.id)


def test_read_doc_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/docs/{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Doc not found"


def test_read_doc_is_shared_with_other_users(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.get(
        f"{settings.API_V1_STR}/docs/{doc.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 200


def test_read_docs(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    create_random_doc(db, box_id=box.id)
    create_random_doc(db, box_id=box.id)
    response = client.get(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/", headers=superuser_token_headers
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


def test_update_doc_fields_in_unclaimed_box(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
        json={"name": "Updated", "pages": 99},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Updated"
    assert content["pages"] == 99


def test_update_doc_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/docs/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"name": "x"},
    )
    assert response.status_code == 404


def test_update_doc_in_box_claimed_by_someone_else(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    doc = create_random_doc(db)
    assert _claim(client, superuser_token_headers, str(doc.box_id)).status_code == 200
    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
        json={"name": "Updated"},
    )
    assert response.status_code == 403


def test_delete_doc(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.delete(
        f"{settings.API_V1_STR}/docs/{doc.id}", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Doc deleted successfully"


def test_delete_doc_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/docs/{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404


def test_delete_doc_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.delete(
        f"{settings.API_V1_STR}/docs/{doc.id}", headers=normal_user_token_headers
    )
    assert response.status_code == 403


# --- Completion ---


def test_complete_doc_requires_claiming_the_box(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = _complete(client, normal_user_token_headers, str(doc.id))
    assert response.status_code == 403
    assert response.json()["detail"] == "Claim this box before completing its docs"


def test_complete_doc_records_who_and_when(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc_a = create_random_doc(db, box_id=box.id)
    create_random_doc(db, box_id=box.id)
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200

    response = _complete(client, normal_user_token_headers, str(doc_a.id))
    assert response.status_code == 200
    content = response.json()
    assert content["completed"] is True
    assert content["prepared_at"] is not None
    assert content["prepared_by_name"] is not None


def test_uncomplete_doc_clears_completion(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc_a = create_random_doc(db, box_id=box.id)
    create_random_doc(db, box_id=box.id)
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    assert _complete(client, normal_user_token_headers, str(doc_a.id)).status_code == 200

    response = _complete(client, normal_user_token_headers, str(doc_a.id), value=False)
    assert response.status_code == 200
    content = response.json()
    assert content["completed"] is False
    assert content["prepared_at"] is None
    assert content["prepared_by_name"] is None


def test_editing_other_fields_keeps_completion_intact(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc_a = create_random_doc(db, box_id=box.id)
    create_random_doc(db, box_id=box.id)
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    completed = _complete(client, normal_user_token_headers, str(doc_a.id)).json()

    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc_a.id}",
        headers=normal_user_token_headers,
        json={"name": "Renamed"},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Renamed"
    assert content["prepared_at"] == completed["prepared_at"]
    assert content["prepared_by_name"] == completed["prepared_by_name"]


def test_superuser_can_complete_without_claiming(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc_a = create_random_doc(db, box_id=box.id)
    create_random_doc(db, box_id=box.id)
    response = _complete(client, superuser_token_headers, str(doc_a.id))
    assert response.status_code == 200
    assert response.json()["prepared_by_name"] is not None

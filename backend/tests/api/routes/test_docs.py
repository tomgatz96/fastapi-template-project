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
    data = {"name": "Foo", "description": "Fighters", "completed": False, "pages": 25}
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
    assert content["assignee_id"] is None
    assert content["assignee_name"] is None
    assert "id" in content
    assert content["pages"] == 25


def test_create_doc_in_another_users_box(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Boxes are shared, so anyone may add a doc to any box."""
    box = create_random_box(db)
    data = {"name": "Foo", "description": "Fighters", "completed": False, "pages": 3}
    response = client.post(
        f"{settings.API_V1_STR}/boxes/{box.id}/docs/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["box_id"] == str(box.id)
    assert content["assignee_id"] is None


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


def test_read_doc_is_shared_with_other_users(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = client.get(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(doc.id)


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
    data = {"name": "Updated", "description": "Updated desc", "completed": True, "pages": 99}
    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["completed"] is True
    assert content["pages"] == 99


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


def test_update_doc_by_other_user_is_allowed(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """Docs in a shared box can be edited by any authenticated user."""
    doc = create_random_doc(db)
    data = {"name": "Updated", "description": "Updated desc", "completed": True}
    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


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


# --- Claiming ---


def _claim(client: TestClient, headers: dict[str, str], doc_id: str):
    return client.post(f"{settings.API_V1_STR}/docs/{doc_id}/claim", headers=headers)


def _unclaim(client: TestClient, headers: dict[str, str], doc_id: str):
    return client.post(f"{settings.API_V1_STR}/docs/{doc_id}/unclaim", headers=headers)


def test_claim_doc_assigns_to_caller(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = _claim(client, normal_user_token_headers, str(doc.id))
    assert response.status_code == 200
    content = response.json()
    assert content["assignee_id"] is not None
    assert content["assignee_name"] is not None


def test_claim_doc_twice_by_same_user_is_ok(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    first = _claim(client, normal_user_token_headers, str(doc.id))
    second = _claim(client, normal_user_token_headers, str(doc.id))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["assignee_id"] == second.json()["assignee_id"]


def test_claim_doc_already_claimed_by_someone_else(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    doc = create_random_doc(db)
    assert _claim(client, superuser_token_headers, str(doc.id)).status_code == 200
    response = _claim(client, normal_user_token_headers, str(doc.id))
    assert response.status_code == 409
    assert response.json()["detail"] == "This doc is already claimed by another user"


def test_claim_doc_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = _claim(client, normal_user_token_headers, str(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["detail"] == "Doc not found"


def test_unclaim_doc_by_assignee(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    assert _claim(client, normal_user_token_headers, str(doc.id)).status_code == 200
    response = _unclaim(client, normal_user_token_headers, str(doc.id))
    assert response.status_code == 200
    content = response.json()
    assert content["assignee_id"] is None
    assert content["assignee_name"] is None


def test_unclaim_doc_that_is_not_claimed(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    doc = create_random_doc(db)
    response = _unclaim(client, normal_user_token_headers, str(doc.id))
    assert response.status_code == 409
    assert response.json()["detail"] == "This doc is not claimed"


def test_unclaim_doc_claimed_by_someone_else(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    doc = create_random_doc(db)
    assert _claim(client, superuser_token_headers, str(doc.id)).status_code == 200
    response = _unclaim(client, normal_user_token_headers, str(doc.id))
    assert response.status_code == 403
    assert response.json()["detail"] == "You can only release a doc assigned to you"


def test_superuser_can_unclaim_any_doc(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    doc = create_random_doc(db)
    assert _claim(client, normal_user_token_headers, str(doc.id)).status_code == 200
    response = _unclaim(client, superuser_token_headers, str(doc.id))
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


def test_update_doc_cannot_change_assignee(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    """assignee_id is not part of DocUpdate, so PUT must not set it."""
    doc = create_random_doc(db)
    me = client.get(
        f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers
    ).json()

    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
        json={"name": "Sneaky", "assignee_id": me["id"]},
    )
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


def test_completed_doc_reports_assignee(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """A claimed and completed doc carries the assignee name for display."""
    doc = create_random_doc(db)
    assert _claim(client, normal_user_token_headers, str(doc.id)).status_code == 200
    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc.id}",
        headers=normal_user_token_headers,
        json={"completed": True},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["completed"] is True
    assert content["assignee_name"] is not None

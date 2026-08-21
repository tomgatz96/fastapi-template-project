"""
The document pipeline: preparation -> scan -> quality control -> completed.
"""

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


def _claim(client: TestClient, headers: dict[str, str], box_id: str):
    return client.post(f"{settings.API_V1_STR}/boxes/{box_id}/claim", headers=headers)


def _unclaim(client: TestClient, headers: dict[str, str], box_id: str):
    return client.post(f"{settings.API_V1_STR}/boxes/{box_id}/unclaim", headers=headers)


def _reject(client: TestClient, headers: dict[str, str], box_id: str):
    return client.post(f"{settings.API_V1_STR}/boxes/{box_id}/reject", headers=headers)


def _add_doc(client: TestClient, headers: dict[str, str], box_id: str, name=None):
    r = client.post(
        f"{settings.API_V1_STR}/boxes/{box_id}/docs/",
        headers=headers,
        json={
            "name": name or random_lower_string(),
            "description": "d",
            "pages": 5,
        },
    )
    assert r.status_code == 200
    return r.json()


def _complete(client: TestClient, headers: dict[str, str], doc_id: str, value=True):
    return client.put(
        f"{settings.API_V1_STR}/docs/{doc_id}",
        headers=headers,
        json={"completed": value},
    )


def _get_box(client: TestClient, headers: dict[str, str], box_id: str):
    r = client.get(f"{settings.API_V1_STR}/boxes/{box_id}", headers=headers)
    assert r.status_code == 200
    return r.json()


def _get_docs(client: TestClient, headers: dict[str, str], box_id: str):
    r = client.get(f"{settings.API_V1_STR}/boxes/{box_id}/docs/", headers=headers)
    assert r.status_code == 200
    return r.json()["data"]


def _finish_stage(client: TestClient, headers: dict[str, str], box_id: str):
    """Claim the box, complete every doc for the current stage."""
    assert _claim(client, headers, box_id).status_code == 200
    for doc in _get_docs(client, headers, box_id):
        assert _complete(client, headers, doc["id"]).status_code == 200


# --- Stage progression ---


def test_new_box_starts_in_preparation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        headers=superuser_token_headers,
        json={"name": random_lower_string(), "description": "new"},
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "preparation"
    assert response.json()["completed"] is False


def test_box_advances_through_every_stage(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(box.id), name=f"A-{random_lower_string()}")
    _add_doc(client, normal_user_token_headers, str(box.id), name=f"B-{random_lower_string()}")

    _finish_stage(client, normal_user_token_headers, str(box.id))
    assert _get_box(client, normal_user_token_headers, str(box.id))["stage"] == "scan"

    _finish_stage(client, normal_user_token_headers, str(box.id))
    assert (
        _get_box(client, normal_user_token_headers, str(box.id))["stage"]
        == "quality_control"
    )

    _finish_stage(client, normal_user_token_headers, str(box.id))
    final = _get_box(client, normal_user_token_headers, str(box.id))
    assert final["stage"] == "completed"
    assert final["completed"] is True
    assert final["assignee_id"] is None


def test_box_stays_in_stage_until_every_doc_is_done(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc_a = _add_doc(client, normal_user_token_headers, str(box.id), name=f"A-{random_lower_string()}")
    _add_doc(client, normal_user_token_headers, str(box.id), name=f"B-{random_lower_string()}")
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200

    _complete(client, normal_user_token_headers, doc_a["id"])
    content = _get_box(client, normal_user_token_headers, str(box.id))
    assert content["stage"] == "preparation"
    assert content["stage_done_count"] == 1
    assert content["doc_count"] == 2
    assert content["assignee_id"] is not None


def test_advancing_resets_doc_completion_for_next_stage(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """A doc prepared in preparation is not yet done for scanning."""
    box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(box.id))
    _finish_stage(client, normal_user_token_headers, str(box.id))

    docs = _get_docs(client, normal_user_token_headers, str(box.id))
    assert docs[0]["completed"] is False
    assert docs[0]["prepared_at"] is not None
    assert docs[0]["scanned_at"] is None


def test_each_stage_records_who_and_when(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(box.id))

    for _ in range(3):
        _finish_stage(client, normal_user_token_headers, str(box.id))

    doc = _get_docs(client, normal_user_token_headers, str(box.id))[0]
    for at_field, by_field in (
        ("prepared_at", "prepared_by_name"),
        ("scanned_at", "scanned_by_name"),
        ("checked_at", "checked_by_name"),
    ):
        assert doc[at_field] is not None, at_field
        assert doc[by_field] is not None, by_field


def test_empty_box_never_advances(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    content = _get_box(client, normal_user_token_headers, str(box.id))
    assert content["stage"] == "preparation"


def test_uncompleting_a_doc_clears_its_stage_record(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc_a = _add_doc(client, normal_user_token_headers, str(box.id), name=f"A-{random_lower_string()}")
    _add_doc(client, normal_user_token_headers, str(box.id), name=f"B-{random_lower_string()}")
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200

    _complete(client, normal_user_token_headers, doc_a["id"])
    response = _complete(client, normal_user_token_headers, doc_a["id"], value=False)
    assert response.status_code == 200
    content = response.json()
    assert content["completed"] is False
    assert content["prepared_at"] is None
    assert content["prepared_by_name"] is None


# --- Filtering by stage ---


def test_boxes_can_be_filtered_by_stage(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    prep_box = create_random_box(db)
    scan_box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(scan_box.id))
    _finish_stage(client, normal_user_token_headers, str(scan_box.id))

    prep = client.get(
        f"{settings.API_V1_STR}/boxes/?stage=preparation",
        headers=normal_user_token_headers,
    ).json()
    scan = client.get(
        f"{settings.API_V1_STR}/boxes/?stage=scan", headers=normal_user_token_headers
    ).json()

    prep_ids = [b["id"] for b in prep["data"]]
    scan_ids = [b["id"] for b in scan["data"]]
    assert str(prep_box.id) in prep_ids
    assert str(scan_box.id) in scan_ids
    assert str(scan_box.id) not in prep_ids


def test_invalid_stage_filter_is_rejected(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/boxes/?stage=nonsense", headers=normal_user_token_headers
    )
    assert response.status_code == 422


# --- Rejection ---


def test_reject_sends_box_back_one_stage(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(box.id))
    _finish_stage(client, normal_user_token_headers, str(box.id))
    _finish_stage(client, normal_user_token_headers, str(box.id))
    assert (
        _get_box(client, normal_user_token_headers, str(box.id))["stage"]
        == "quality_control"
    )

    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    response = _reject(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 200
    content = response.json()
    assert content["stage"] == "scan"
    assert content["assignee_id"] is None


def test_reject_clears_the_returned_stage_records(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(box.id))
    _finish_stage(client, normal_user_token_headers, str(box.id))
    _finish_stage(client, normal_user_token_headers, str(box.id))
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    _reject(client, normal_user_token_headers, str(box.id))

    doc = _get_docs(client, normal_user_token_headers, str(box.id))[0]
    assert doc["scanned_at"] is None
    assert doc["scanned_by_name"] is None
    assert doc["checked_at"] is None
    assert doc["prepared_at"] is not None


def test_reject_requires_holding_the_box(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    box = create_random_box(db)
    _add_doc(client, superuser_token_headers, str(box.id))
    _finish_stage(client, superuser_token_headers, str(box.id))
    assert _unclaim(client, superuser_token_headers, str(box.id)).status_code in (
        200,
        409,
    )

    response = _reject(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 403
    assert response.json()["detail"] == "Claim this box before sending it back"


def test_reject_from_preparation_is_rejected(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    response = _reject(client, normal_user_token_headers, str(box.id))
    assert response.status_code == 409
    assert "first stage" in response.json()["detail"]


def test_rejected_box_can_be_reworked_and_advance_again(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(box.id))
    _finish_stage(client, normal_user_token_headers, str(box.id))
    _finish_stage(client, normal_user_token_headers, str(box.id))
    assert _claim(client, normal_user_token_headers, str(box.id)).status_code == 200
    _reject(client, normal_user_token_headers, str(box.id))

    _finish_stage(client, normal_user_token_headers, str(box.id))
    assert (
        _get_box(client, normal_user_token_headers, str(box.id))["stage"]
        == "quality_control"
    )


# --- Completed boxes are frozen ---


def test_completed_box_cannot_be_claimed(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    box = create_random_box(db)
    _add_doc(client, normal_user_token_headers, str(box.id))
    for _ in range(3):
        _finish_stage(client, normal_user_token_headers, str(box.id))

    response = _claim(client, superuser_token_headers, str(box.id))
    assert response.status_code == 409
    assert response.json()["detail"] == "This box is already completed"


def test_completed_box_docs_cannot_be_edited(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    box = create_random_box(db)
    doc = _add_doc(client, normal_user_token_headers, str(box.id))
    for _ in range(3):
        _finish_stage(client, normal_user_token_headers, str(box.id))

    response = client.put(
        f"{settings.API_V1_STR}/docs/{doc['id']}",
        headers=normal_user_token_headers,
        json={"name": random_lower_string()},
    )
    assert response.status_code == 403

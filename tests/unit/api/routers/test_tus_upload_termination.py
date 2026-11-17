"""A TUS termination request can delete only an upload in progress.

``DELETE /tus/{uuid}`` removes whatever file of that name sits in the router's
working directory, and accepts any signed-in user. Finished uploads are kept under
their content hash (``finalize_file_from_path``), so the working directory must not
be the one they are stored in, or a signed-in user could delete another project's
document by naming it.
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers.tus_upload import _get_pre_create_hook, tus_router
from lib.config.env import config
from lib.models.user import User

TUS = {"Tus-Resumable": "1.0.0"}


async def _accept(metadata: dict, upload_info: dict) -> None:
    """The project checks are covered elsewhere; any upload may start here."""


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(tus_router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid.uuid4(), email="someone@example.com"
    )
    app.dependency_overrides[_get_pre_create_hook] = lambda: _accept
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def stored_document() -> Iterator[str]:
    """A finished upload where ``finalize_file_from_path`` keeps one."""

    os.makedirs(config.FILE_UPLOADS_MOUNT_PATH, exist_ok=True)
    name = uuid.uuid4().hex + ".pdf"
    path = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, name)
    with open(path, "wb") as file:
        file.write(b"%PDF-1.4 someone else's document")
    yield name
    if os.path.exists(path):
        os.remove(path)


def test_cannot_delete_a_stored_document(
    client: TestClient, stored_document: str
) -> None:
    client.delete(f"/tus/{stored_document}", headers=TUS)

    path = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, stored_document)
    assert os.path.exists(path)


def test_deletes_an_upload_in_progress(client: TestClient) -> None:
    created = client.post(
        "/tus",
        headers={**TUS, "Upload-Length": "10"},
    )
    assert created.status_code == 201, created.text
    upload_id = created.headers["Location"].rstrip("/").rsplit("/", 1)[-1]

    deleted = client.delete(f"/tus/{upload_id}", headers=TUS)

    assert deleted.status_code == 204
    assert client.head(f"/tus/{upload_id}", headers=TUS).status_code == 404

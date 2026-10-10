import io
import json

import pytest
from django.test import Client

from apps.content import services as content
from apps.media.models import MediaFile

from .conftest import doc

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00"
    b"\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def translation(private_collection, editor):
    return content.create_article(private_collection, title="Doc", language="fr", user=editor)


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": tmp_path},
        },
    }
    return tmp_path


def test_autosave_draft(client, editor, translation):
    client.force_login(editor)
    url = f"/api/translations/{translation.pk}/draft"
    payload = {"title": "Doc v2", "content": doc("Sauvé")}
    response = client.put(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 200, response.content
    translation.refresh_from_db()
    assert translation.draft_title == "Doc v2"
    assert translation.draft_content == doc("Sauvé")
    response = client.get(f"/api/translations/{translation.pk}")
    assert response.json()["title"] == "Doc v2"


def test_autosave_requires_csrf(editor, translation):
    client = Client(enforce_csrf_checks=True)
    client.force_login(editor)
    response = client.put(
        f"/api/translations/{translation.pk}/draft",
        json.dumps({"title": "x", "content": doc("x")}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_autosave_rights(client, reader, translation):
    client.force_login(reader)
    response = client.put(
        f"/api/translations/{translation.pk}/draft",
        json.dumps({"title": "x", "content": doc("x")}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_autosave_validates_document(client, editor, translation):
    client.force_login(editor)
    response = client.put(
        f"/api/translations/{translation.pk}/draft",
        json.dumps({"title": "x", "content": {"type": "nope"}}),
        content_type="application/json",
    )
    assert response.status_code == 422


def upload(client, collection, name="pic.png", data=PNG, content_type="image/png"):
    file = io.BytesIO(data)
    file.name = name
    return client.post(f"/api/collections/{collection.pk}/media", {"file": file})


def test_upload_and_serve_private_file(client, editor, reader, outsider, private_collection):
    client.force_login(editor)
    response = upload(client, private_collection)
    assert response.status_code == 201, response.content
    url = response.json()["url"]
    assert url.startswith("/files/")

    client.force_login(reader)
    served = client.get(url)
    assert served.status_code == 200
    assert served["Content-Type"] == "image/png"
    assert "private" in served["Cache-Control"]

    client.force_login(outsider)
    assert client.get(url).status_code == 404
    client.logout()
    assert client.get(url).status_code == 404


def test_public_file_is_public(client, editor, public_collection):
    client.force_login(editor)
    url = upload(client, public_collection).json()["url"]
    client.logout()
    assert client.get(url).status_code == 200


def test_upload_rejects_other_types(client, editor, private_collection):
    client.force_login(editor)
    response = client.post(
        f"/api/collections/{private_collection.pk}/media",
        {"file": io.BytesIO(b"<svg onload=alert(1)>")},
    )
    assert response.status_code in (422, 400)
    assert not MediaFile.objects.exists()


def test_glossary_api(client, editor, private_collection):
    from apps.i18n.models import GlossaryTerm

    GlossaryTerm.objects.create(translations={"fr": "clé", "de": "Schlüssel"})
    client.force_login(editor)
    data = client.get("/api/glossary").json()
    assert data[0]["translations"]["de"] == "Schlüssel"
    assert data[0]["translations"]["en"] == ""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp.close()
    tmp_path = tmp.name

    from app.config import Settings

    _original = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None

    from app import config as cfg_mod

    prev = cfg_mod.settings
    from app.config import settings as s

    s.duckdb_path = tmp_path
    s.vector_backend = "duckdb"

    from app import database as db_mod

    db_mod.store = db_mod.DocStore()

    from app.main import app

    c = TestClient(app)
    yield c

    Settings.model_config["env_file"] = _original
    cfg_mod.settings = prev
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["app"] == "ok"
    assert "documents_count" in data


def test_create_document(client):
    r = client.post(
        "/documents",
        json={"source": "test.txt", "content": "Kebijakan cuti karyawan adalah 12 hari per tahun."},
    )
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert body["source"] == "test.txt"
    return body["id"]


def test_get_document(client):
    doc_id = test_create_document(client)
    r = client.get(f"/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["id"] == doc_id


def test_get_document_not_found(client):
    r = client.get("/documents/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_list_documents(client):
    test_create_document(client)
    r = client.get("/documents", params={"limit": 10})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_update_document(client):
    doc_id = test_create_document(client)
    r = client.put(
        f"/documents/{doc_id}",
        json={"source": "test_v2.txt", "content": "Kebijakan cuti diperbarui menjadi 15 hari."},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "test_v2.txt"


def test_delete_document(client):
    doc_id = test_create_document(client)
    r = client.delete(f"/documents/{doc_id}")
    assert r.status_code == 200
    r2 = client.get(f"/documents/{doc_id}")
    assert r2.status_code == 404


def test_bulk_create(client):
    r = client.post(
        "/documents/bulk",
        json=[
            {"source": "a.txt", "content": "Isi A"},
            {"source": "b.txt", "content": "Isi B"},
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["inserted"] == 2
    assert len(body["ids"]) == 2


def test_search_documents(client):
    client.post(
        "/documents",
        json={"source": "sop.txt", "content": "SOP klaim garansi: hubungi CS, kirim unit, tunggu perbaikan."},
    )
    r = client.get("/documents/search", params={"q": "klaim garansi", "k": 3})
    assert r.status_code == 200
    results = r.json()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "score" in results[0]


def test_ingest_text_chunked(client):
    long_content = " ".join(["kalimat"] * 1000)
    r = client.post(
        "/documents/ingest-text",
        params={"chunk_size": 200, "chunk_overlap": 40},
        json={"source": "long.txt", "content": long_content},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_chunks"] >= 5
    assert len(body["document_ids"]) == body["total_chunks"]

"""Phase 1 smoke and integration tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.store import store


def setup_module(module):  # noqa: ARG001
    # Lifespan does not run with TestClient unless we use 'with'; ensure data loaded.
    if not store.documents:
        store.load()


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["documents_loaded"] > 0


def test_list_documents():
    r = client.get("/api/documents?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 5
    assert body["total"] > 0
    assert len(body["items"]) <= 5
    first = body["items"][0]
    assert "document_id" in first
    assert "title" in first


def test_get_document_roundtrip():
    listing = client.get("/api/documents?limit=1").json()
    doc_id = listing["items"][0]["document_id"]
    r = client.get(f"/api/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["document_id"] == doc_id


def test_get_document_404():
    r = client.get("/api/documents/does-not-exist")
    assert r.status_code == 404


def test_search():
    r = client.get("/api/search?query=fbi")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert any("fbi" in (item["title"] + (item["description"] or "")).lower() or
               (item["agency"] or "").lower() == "fbi"
               for item in body["items"])


def test_facets():
    r = client.get("/api/facets")
    assert r.status_code == 200
    body = r.json()
    assert "agency" in body
    assert "file_type" in body
    assert any(f["value"].lower() == "pdf" for f in body["file_type"])


def test_stats():
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_records"] > 0
    assert body["pdfs"] > 0
    assert body["agencies"] >= 1


def test_missing_values_handled():
    docs = client.get("/api/documents?limit=500").json()["items"]
    # At least one record should have N/A incident date that we mapped to None.
    assert any(d["incident_date"] is None for d in docs)

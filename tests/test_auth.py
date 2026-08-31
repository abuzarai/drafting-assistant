"""Inbound auth tests for the drafting service (X-Internal-Key in production)."""

import os

os.environ["ENV"] = "production"
os.environ["INTERNAL_API_KEY"] = "test-internal-key"

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

# No context manager: skips lifespan so no DB pool is opened in tests.
client = TestClient(app)


def test_health_stays_public():
    assert client.get("/health").status_code == 200


def test_draft_requires_key():
    resp = client.post("/draft/generate", json={})
    assert resp.status_code == 401


def test_draft_with_key_reaches_handler():
    # Dependency passes; body validation then runs (proving it's not a 401).
    resp = client.post(
        "/draft/generate",
        json={},
        headers={"x-internal-key": "test-internal-key"},
    )
    assert resp.status_code != 401


def test_docs_disabled_in_production():
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
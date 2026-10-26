"""Synthetic contract coverage for Stage A; no provider or database execution."""

import asyncio
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from config import settings
from main import app
from services import context_service
from services.draft_jobs import JobStore, jobs

AUTH = {"x-internal-key": "test-internal-key"}
SCOPE = {"case_id": 101, "advocate_id": 77}


@pytest.fixture
def recorded_job(monkeypatch):
    monkeypatch.setattr(jobs, "_jobs", {
        "known-job": {
            **SCOPE, "status": "succeeded", "result": {"draft": "fictional"},
            "error": None, "created": time.monotonic(), "ttl": 1800,
        }
    })
    return "known-job"


@pytest.mark.parametrize("params", [{}, {"case_id": 101}, {"case_id": -1, "advocate_id": 77}])
def test_poll_requires_positive_scope(params):
    response = TestClient(app).get("/draft/generate/known-job", params=params, headers=AUTH)
    assert response.status_code == 422


@pytest.mark.parametrize("params", [
    {"case_id": 102, "advocate_id": 77}, {"case_id": 101, "advocate_id": 78},
])
def test_poll_hides_other_case_or_actor(recorded_job, params, monkeypatch):
    async def unexpected(*args):
        pytest.fail("Mismatched job scope must fail before context access")
    monkeypatch.setattr(context_service, "get_case_context", unexpected)
    response = TestClient(app).get(f"/draft/generate/{recorded_job}", params=params, headers=AUTH)
    assert response.status_code == 404
    assert "fictional" not in response.text


@pytest.mark.parametrize("revoked", [False, True])
def test_poll_rechecks_current_case_access(recorded_job, monkeypatch, revoked):
    calls = []
    async def check(case_id, advocate_id):
        calls.append((case_id, advocate_id))
        if revoked:
            raise PermissionError("Assignment revoked")
        return {"id": case_id}
    monkeypatch.setattr(context_service, "get_case_context", check)
    response = TestClient(app).get(f"/draft/generate/{recorded_job}", params=SCOPE, headers=AUTH)
    assert response.status_code == (403 if revoked else 200)
    assert calls == [(101, 77)]
    if revoked:
        assert "fictional" not in response.text


def test_generation_denied_before_job_allocation(monkeypatch):
    async def deny(*args):
        raise PermissionError("Not assigned")
    monkeypatch.setattr(context_service, "get_case_context", deny)
    monkeypatch.setattr(jobs, "create", lambda *a, **k: pytest.fail("Allocated unauthorized job"))
    response = TestClient(app).post("/draft/generate", headers=AUTH, json={
        **SCOPE, "document_type": "Plaint", "language": "English",
    })
    assert response.status_code == 403


def test_job_store_preserves_scope_without_exposing_it():
    async def exercise():
        store = JobStore()
        async def result():
            return {"draft": "fictional"}
        job_id = store.create(result, **SCOPE)
        await asyncio.sleep(0)
        assert store.get(job_id, **SCOPE)["status"] == "succeeded"
        assert store.get(job_id, case_id=102, advocate_id=77) is None
        assert store.get(job_id, case_id=101, advocate_id=78) is None
        assert "advocate_id" not in store.get(job_id, **SCOPE)
    asyncio.run(exercise())


@pytest.mark.parametrize("env", ["local", "production"])
def test_all_context_and_save_calls_use_express(monkeypatch, env):
    monkeypatch.setattr(settings, "env", env)
    calls = []
    real_client = httpx.AsyncClient
    def handle(request):
        import json
        calls.append((request.url.path, json.loads(request.content), request.headers["x-internal-key"]))
        return httpx.Response(200, json={"saved": True, "case_documents": [], "client_documents": []})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(
        **kw, transport=httpx.MockTransport(handle),
    ))
    async def exercise():
        await context_service.get_case_context(101, 77)
        await context_service.get_intake_analysis(101, 77)
        await context_service.get_case_documents(101, 77)
        assert await context_service.save_draft_session(101, "Plaint", "fictional-gen", {}, 77)
    asyncio.run(exercise())
    assert [path for path, _, _ in calls] == [
        "/internal/draft/case-context", "/internal/draft/intake-analysis",
        "/internal/draft/documents", "/internal/draft/save",
    ]
    assert all(payload["case_id"] == 101 and payload["advocate_id"] == 77 for _, payload, _ in calls)
    assert all(key == "test-internal-key" for _, _, key in calls)
    assert "user_id" not in calls[2][1]


@pytest.mark.parametrize("env", ["local", "production"])
def test_missing_internal_key_fails_closed(monkeypatch, env):
    monkeypatch.setattr(settings, "env", env)
    monkeypatch.setattr(settings, "internal_api_key", "")
    response = TestClient(app).post("/draft/init", json=SCOPE)
    assert response.status_code == 503


@pytest.mark.parametrize("field", ["internal_api_key", "express_internal_url"])
def test_startup_requires_express_without_opening_db(monkeypatch, field):
    monkeypatch.setattr(settings, field, "")
    with pytest.raises(RuntimeError, match="Drafting requires"):
        with TestClient(app):
            pass


def test_configured_startup_needs_no_database():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("status", [403, 404, 409])
def test_save_preserves_resource_errors(monkeypatch, status):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(
        **kw, transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": "Denied"})
        ),
    ))
    response = TestClient(app).post("/draft/save", headers=AUTH, json={
        **SCOPE, "document_type": "Plaint", "generation_id": "fictional-gen",
        "draft": {"title": "Fictional", "sections": []},
    })
    assert response.status_code == status

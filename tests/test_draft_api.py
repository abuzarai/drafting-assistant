from io import BytesIO

import os

os.environ.setdefault("ENV", "production")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")

from fastapi.testclient import TestClient

import main as draft_main


AUTH = {"x-internal-key": os.environ["INTERNAL_API_KEY"]}


def _mock_prefilled_fields():
    return {
        "plaintiff": "Ali Raza",
        "defendant": "ABC Builders",
        "advocate": "Ayesha Khan",
        "nature_of_dispute": "Property possession dispute",
        "relief_sought": "Permanent injunction",
        "key_facts": "Builder encroached client land in Lahore",
    }


async def _noop_async(*_args, **_kwargs):
    return None


def _build_client():
    draft_main.init_pool = _noop_async
    draft_main.close_pool = _noop_async
    return TestClient(draft_main.app)


def test_health_returns_service_status():
    client = _build_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "drafting-assistant"


def test_draft_init_success(monkeypatch):
    client = _build_client()
    monkeypatch.setattr("routes.draft.get_pool", lambda: object())

    async def _get_case_context(*_args, **_kwargs):
        return {
            "user_id": 501,
            "current_stage": "notice",
            "name": "Ali Raza",
            "language": "English",
        }

    async def _get_intake_analysis(*_args, **_kwargs):
        return {
            "analysis": {"issue": "encroachment"},
            "transcript": "Client reports land encroachment",
        }

    async def _get_case_documents(*_args, **_kwargs):
        return {"case_documents": [], "client_documents": []}

    monkeypatch.setattr(
        "routes.draft.context_service.get_case_context", _get_case_context
    )
    monkeypatch.setattr(
        "routes.draft.context_service.get_intake_analysis", _get_intake_analysis
    )
    monkeypatch.setattr(
        "routes.draft.context_service.get_case_documents", _get_case_documents
    )
    monkeypatch.setattr(
        "routes.draft.context_service.get_document_type",
        lambda *_args, **_kwargs: "Legal Notice",
    )
    monkeypatch.setattr(
        "routes.draft.context_service.build_prefilled_fields",
        lambda *_args, **_kwargs: _mock_prefilled_fields(),
    )
    monkeypatch.setattr(
        "routes.draft.context_service.get_missing_documents",
        lambda *_args, **_kwargs: ["Title deed"],
    )

    response = client.post("/draft/init", json={"case_id": 101, "advocate_id": 77}, headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == 101
    assert body["document_type"] == "Legal Notice"
    assert body["prefilled_fields"]["plaintiff"] == "Ali Raza"
    assert body["missing_documents"] == ["Title deed"]


def test_draft_generate_success(monkeypatch):
    client = _build_client()
    monkeypatch.setattr("routes.draft.get_pool", lambda: object())

    async def _get_case_context(*_args, **_kwargs):
        return {"user_id": 501, "name": "Ali Raza"}

    async def _get_intake_analysis(*_args, **_kwargs):
        return {
            "analysis": {"issue": "encroachment"},
            "transcript": "Client reports land encroachment",
        }

    async def _get_case_documents(*_args, **_kwargs):
        return {"case_documents": [], "client_documents": []}

    class Prefilled:
        nature_of_dispute = "Property encroachment"

        def model_dump(self):
            return _mock_prefilled_fields()

    async def _query_legal_references(*_args, **_kwargs):
        return "Order VII Rule 11 CPC"

    async def _generate_draft(*_args, **_kwargs):
        return (
            {
                "title": "Draft Legal Notice",
                "sections": [
                    {"id": "s1", "heading": "Facts", "content": "Facts content"}
                ],
            },
            "gen-123",
        )

    monkeypatch.setattr(
        "routes.draft.context_service.get_case_context", _get_case_context
    )
    monkeypatch.setattr(
        "routes.draft.context_service.get_intake_analysis", _get_intake_analysis
    )
    monkeypatch.setattr(
        "routes.draft.context_service.get_case_documents", _get_case_documents
    )
    monkeypatch.setattr(
        "routes.draft.context_service.build_prefilled_fields",
        lambda *_args, **_kwargs: Prefilled(),
    )
    monkeypatch.setattr(
        "routes.draft.context_service.build_document_context",
        lambda *_args, **_kwargs: "doc context",
    )
    monkeypatch.setattr(
        "routes.draft.context_service.build_balanced_case_context",
        lambda *_args, **_kwargs: "balanced context",
    )
    monkeypatch.setattr(
        "routes.draft.rag_service.query_legal_references", _query_legal_references
    )
    monkeypatch.setattr("routes.draft.gemini_service.generate_draft", _generate_draft)

    response = client.post(
        "/draft/generate",
        json={
            "case_id": 101,
            "advocate_id": 77,
            "document_type": "Legal Notice",
            "advocate_notes": "Urgent matter",
            "language": "English",
        },
        headers=AUTH,
    )

    # Generation is queued as a background job; poll for the result.
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"

    import time

    body = None
    for _ in range(50):
        status_resp = client.get(f"/draft/generate/{job_id}", headers=AUTH)
        assert status_resp.status_code == 200
        body = status_resp.json()
        if body["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)

    assert body["status"] == "succeeded"
    result = body["result"]
    assert result["generation_id"] == "gen-123"
    assert result["document_type"] == "Legal Notice"
    assert result["draft"]["title"] == "Draft Legal Notice"


def test_draft_generate_status_404():
    client = _build_client()
    assert client.get("/draft/generate/does-not-exist", headers=AUTH).status_code == 404


def test_draft_export_rejects_non_docx():
    client = _build_client()
    response = client.post(
        "/draft/export",
        json={
            "case_id": 101,
            "document_type": "Legal Notice",
            "format": "pdf",
            "final_draft": {
                "title": "Draft",
                "sections": [{"id": "s1", "heading": "Facts", "content": "Sample"}],
            },
        },
        headers=AUTH,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Only docx export is supported"


def test_draft_export_docx_success(monkeypatch):
    client = _build_client()
    monkeypatch.setattr(
        "routes.draft.export_service.generate_docx",
        lambda *_args, **_kwargs: BytesIO(b"docx bytes"),
    )

    response = client.post(
        "/draft/export",
        json={
            "case_id": 101,
            "document_type": "Legal Notice",
            "format": "docx",
            "final_draft": {
                "title": "Draft",
                "sections": [{"id": "s1", "heading": "Facts", "content": "Sample"}],
            },
        },
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

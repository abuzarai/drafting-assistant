"""Context service with local DB and production proxy modes."""

import logging
import json
from typing import Any

import httpx

from config import settings
from models.schemas import PrefilledFields

logger = logging.getLogger(__name__)

STAGE_DOCUMENT_MAP = {
    "pre_acceptance": "Client-Lawyer Contract",
    "case_active": "Plaint",
    "filing": "Plaint",
    "response_stage": "Written Statement",
    "maintainability": "Objection Response",
    "evidence_stage": "Affidavit",
    "appeal": "Appeal Application",
}

DEFAULT_DOCUMENT_TYPE = "Plaint"

REQUIRED_DOCS_MAP = {
    "Plaint": ["CNIC_FRONT", "CNIC_BACK", "FIR_COPY", "EVIDENCE"],
    "Client-Lawyer Contract": [],
    "Written Statement": ["CNIC_FRONT", "CNIC_BACK"],
    "Objection Response": ["CNIC_FRONT"],
    "Affidavit": ["CNIC_FRONT", "AFFIDAVIT"],
    "Appeal Application": ["CNIC_FRONT", "CNIC_BACK", "EVIDENCE"],
    "Notice": ["CNIC_FRONT", "CNIC_BACK"],
    "Misc. Petition": ["CNIC_FRONT", "EVIDENCE"],
    "Application (Stay/Injunction)": ["CNIC_FRONT", "CNIC_BACK", "EVIDENCE"],
}

BALANCED_DOC_CONTEXT_RULES = {
    "Client-Lawyer Contract": {
        "max_docs": 5,
        "max_chars_per_doc": 1100,
        "max_total_chars": 4500,
    },
    "Affidavit": {"max_docs": 5, "max_chars_per_doc": 1200, "max_total_chars": 4800},
    "Notice": {"max_docs": 5, "max_chars_per_doc": 1200, "max_total_chars": 4800},
    "Misc. Petition": {
        "max_docs": 6,
        "max_chars_per_doc": 1300,
        "max_total_chars": 5600,
    },
    "Application (Stay/Injunction)": {
        "max_docs": 6,
        "max_chars_per_doc": 1400,
        "max_total_chars": 6000,
    },
}

DEFAULT_BALANCED_DOC_CONTEXT_RULE = {
    "max_docs": 6,
    "max_chars_per_doc": 1400,
    "max_total_chars": 6200,
}


def _doc_type_key(value: Any) -> str:
    return str(value or "").strip().upper()


def _is_relevant_document_type(target_document_type: str, doc_type: str) -> bool:
    target = str(target_document_type or "").strip()
    normalized = _doc_type_key(doc_type)
    required = {k.upper() for k in REQUIRED_DOCS_MAP.get(target, [])}
    if normalized and normalized in required:
        return True

    broad_relevance = {
        "Client-Lawyer Contract": {"CNIC_FRONT", "CNIC_BACK", "ADDRESS_PROOF", "OTHER"},
        "Plaint": {
            "FIR_COPY",
            "EVIDENCE",
            "CNIC_FRONT",
            "CNIC_BACK",
            "ADDRESS_PROOF",
            "OTHER",
        },
        "Written Statement": {"EVIDENCE", "CNIC_FRONT", "CNIC_BACK", "OTHER"},
        "Affidavit": {"AFFIDAVIT", "EVIDENCE", "CNIC_FRONT", "CNIC_BACK", "OTHER"},
        "Notice": {
            "NOTICE",
            "EVIDENCE",
            "CNIC_FRONT",
            "CNIC_BACK",
            "ADDRESS_PROOF",
            "OTHER",
        },
        "Misc. Petition": {"EVIDENCE", "CNIC_FRONT", "CNIC_BACK", "OTHER"},
        "Application (Stay/Injunction)": {
            "EVIDENCE",
            "CNIC_FRONT",
            "CNIC_BACK",
            "FIR_COPY",
            "OTHER",
        },
    }
    return normalized in broad_relevance.get(target, set())


def _safe_get(value: Any, key: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return default


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def get_document_type(current_stage: str | None) -> str:
    return STAGE_DOCUMENT_MAP.get(current_stage, DEFAULT_DOCUMENT_TYPE)


def build_prefilled_fields(
    analysis_json: dict[str, Any] | None,
    transcript: str | None,
    case_context: dict[str, Any] | None = None,
) -> PrefilledFields:
    analysis = _as_dict(analysis_json)
    ctx = _as_dict(case_context)
    entities = _as_dict(_safe_get(analysis, "key_entities", {}))
    parties = _safe_get(entities, "parties", [])
    locations = _safe_get(entities, "locations", [])
    dates = _safe_get(entities, "dates", [])
    amounts = _safe_get(entities, "amounts", [])

    client_name = str(ctx.get("client_name") or ctx.get("name") or "").strip()
    plaintiff = (
        parties[0]
        if isinstance(parties, list) and len(parties) > 0
        else (client_name or "To be specified")
    )
    defendant = (
        parties[1]
        if isinstance(parties, list) and len(parties) > 1
        else "To be specified"
    )

    issue_summary = _safe_get(analysis, "issue_summary", "")
    legal_domain = _safe_get(analysis, "legal_domain", "")
    nature_of_dispute = issue_summary or legal_domain or "To be specified"

    key_parts: list[str] = []
    if isinstance(locations, list) and locations:
        key_parts.append("Locations: " + ", ".join(str(x) for x in locations))
    if isinstance(dates, list) and dates:
        key_parts.append("Dates: " + ", ".join(str(x) for x in dates))
    if isinstance(amounts, list) and amounts:
        key_parts.append("Amounts: " + ", ".join(str(x) for x in amounts))
    key_facts = " | ".join(key_parts) if key_parts else (transcript or "")

    return PrefilledFields(
        plaintiff=plaintiff,
        defendant=defendant,
        advocate=str(ctx.get("advocate_name") or "To be specified"),
        advocate_email=str(ctx.get("advocate_email") or ""),
        advocate_phone=str(ctx.get("advocate_phone") or ""),
        advocate_bar_council_id=str(ctx.get("advocate_bar_council_id") or ""),
        jurisdiction=None,
        nature_of_dispute=nature_of_dispute,
        relief_sought=None,
        key_facts=key_facts,
    )


def get_missing_documents(
    document_type: str,
    case_documents: list[dict[str, Any]],
    client_documents: list[dict[str, Any]],
) -> list[str]:
    required = REQUIRED_DOCS_MAP.get(document_type, [])
    approved = set()

    for doc in case_documents + client_documents:
        status = str(doc.get("status", "")).lower()
        if status == "approved":
            approved.add(str(doc.get("doc_type", "")).upper())

    return [doc_type for doc_type in required if doc_type.upper() not in approved]


def build_document_context(
    case_documents: list[dict[str, Any]],
    client_documents: list[dict[str, Any]],
    document_type: str,
) -> str:
    rules = BALANCED_DOC_CONTEXT_RULES.get(
        document_type, DEFAULT_BALANCED_DOC_CONTEXT_RULE
    )
    max_chars_per_doc = int(rules.get("max_chars_per_doc", 1200))
    max_docs = int(rules.get("max_docs", 5))
    max_total_chars = int(rules.get("max_total_chars", 4500))

    merged = []
    for doc in case_documents:
        merged.append({**doc, "source": doc.get("source") or "case"})
    for doc in client_documents:
        merged.append({**doc, "source": doc.get("source") or "client"})

    relevant_parts: list[str] = []
    fallback_parts: list[str] = []
    total_chars = 0

    for doc in merged:
        status = str(doc.get("status", "")).strip().lower()
        text = str(doc.get("extracted_text") or "").strip()
        if status != "approved" or not text:
            continue

        doc_type = str(doc.get("doc_type") or "Unknown")
        source = str(doc.get("source") or "unknown")
        file_url = str(doc.get("file_url") or "")
        snippet = text[:max_chars_per_doc]
        if len(text) > max_chars_per_doc:
            snippet += "..."

        note = str(doc.get("note") or "").strip()
        note_line = f"\nnote={note[:240]}" if note else ""

        block = f"[{doc_type}] source={source} file={file_url}{note_line}\n{snippet}"
        block_len = len(block)

        if total_chars + block_len > max_total_chars:
            continue

        if _is_relevant_document_type(document_type, doc_type):
            relevant_parts.append(block)
        else:
            fallback_parts.append(block)

        total_chars += block_len

    selected: list[str] = []
    for item in relevant_parts:
        if len(selected) >= max_docs:
            break
        selected.append(item)

    if len(selected) < max_docs:
        for item in fallback_parts:
            if len(selected) >= max_docs:
                break
            selected.append(item)

    return "\n\n".join(selected) if selected else "No verified documents available."


def build_balanced_case_context(
    case_context: dict[str, Any],
    document_type: str,
    prefilled_fields: PrefilledFields,
) -> str:
    ctx = _as_dict(case_context)
    lines: list[str] = []

    lines.append(f"Case ID: {ctx.get('id')}")
    if ctx.get("title"):
        lines.append(f"Case Title: {ctx.get('title')}")
    if ctx.get("current_stage"):
        lines.append(f"Stage: {ctx.get('current_stage')}")
    if ctx.get("legal_domain"):
        lines.append(f"Legal Domain: {ctx.get('legal_domain')}")

    lines.append(f"Client: {prefilled_fields.plaintiff or 'To be specified'}")
    if prefilled_fields.defendant and prefilled_fields.defendant != "To be specified":
        lines.append(f"Counterparty: {prefilled_fields.defendant}")

    if document_type == "Client-Lawyer Contract":
        if ctx.get("description"):
            lines.append(f"Matter Summary: {str(ctx.get('description'))[:500]}")
        if ctx.get("client_cnic"):
            lines.append(f"Client CNIC: {ctx.get('client_cnic')}")
        if ctx.get("client_email"):
            lines.append(f"Client Email: {ctx.get('client_email')}")
        if ctx.get("client_phone"):
            lines.append(f"Client Phone: {ctx.get('client_phone')}")
        if ctx.get("client_city"):
            lines.append(f"Client City: {ctx.get('client_city')}")
        if ctx.get("client_address"):
            lines.append(f"Client Address: {ctx.get('client_address')}")

        lines.append(f"Advocate: {prefilled_fields.advocate or 'To be specified'}")
        if prefilled_fields.advocate_email:
            lines.append(f"Advocate Email: {prefilled_fields.advocate_email}")
        if prefilled_fields.advocate_phone:
            lines.append(f"Advocate Phone: {prefilled_fields.advocate_phone}")
        if prefilled_fields.advocate_bar_council_id:
            lines.append(
                f"Advocate Bar Council ID: {prefilled_fields.advocate_bar_council_id}"
            )
        if ctx.get("advocate_city"):
            lines.append(f"Advocate City: {ctx.get('advocate_city')}")
        if ctx.get("advocate_court"):
            lines.append(f"Advocate Court: {ctx.get('advocate_court')}")

        if ctx.get("payment_required_total") is not None:
            lines.append(f"Payment Required Total: {ctx.get('payment_required_total')}")
        if ctx.get("payment_verified_total") is not None:
            lines.append(f"Payment Verified Total: {ctx.get('payment_verified_total')}")
        if ctx.get("payment_status"):
            lines.append(f"Payment Status: {ctx.get('payment_status')}")
    else:
        if prefilled_fields.nature_of_dispute:
            lines.append(f"Nature of Dispute: {prefilled_fields.nature_of_dispute}")
        if prefilled_fields.key_facts:
            lines.append(f"Key Facts: {prefilled_fields.key_facts}")

    return "\n".join(lines)


async def _post_internal(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.express_internal_url or not settings.internal_api_key:
        raise RuntimeError(
            "Production mode requires EXPRESS_INTERNAL_URL and INTERNAL_API_KEY"
        )

    url = settings.express_internal_url.rstrip("/") + path
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"X-Internal-Key": settings.internal_api_key},
        )

    if response.status_code == 403:
        raise PermissionError("Advocate not authorized for this case")
    if response.status_code == 404:
        raise LookupError("Case not found")
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


async def get_case_context(case_id: int, advocate_id: int, pool) -> dict[str, Any]:
    if settings.env == "production":
        return await _post_internal(
            "/internal/draft/case-context",
            {"case_id": case_id, "advocate_id": advocate_id},
        )

    if pool is None:
        raise RuntimeError("Database pool is not initialized in local mode")

    row = await pool.fetchrow(
        """
        SELECT
            cc.*,
            cu.name,
            cu.email,
            cu.name AS client_name,
            cu.email AS client_email,
            cp.phone AS client_phone,
            cp.cnic AS client_cnic,
            cp.city AS client_city,
            cp.address AS client_address,
            au.name AS advocate_name,
            au.email AS advocate_email,
            ap.phone AS advocate_phone,
            ap.bar_council_id AS advocate_bar_council_id,
            ap.city AS advocate_city,
            ap.court AS advocate_court
        FROM public.client_cases cc
        JOIN public.users cu ON cc.user_id = cu.id
        LEFT JOIN public.users au ON cc.assigned_advocate_id = au.id
        LEFT JOIN public.client_profiles cp ON cp.user_id = cc.user_id
        LEFT JOIN public.advocate_profiles ap ON ap.user_id = cc.assigned_advocate_id
        WHERE cc.id = $1
        """,
        case_id,
    )

    if not row:
        raise LookupError("Case not found")

    data = dict(row)
    if data.get("assigned_advocate_id") != advocate_id:
        raise PermissionError("Advocate not authorized for this case")

    return data


async def get_intake_analysis(case_id: int, pool) -> dict[str, Any]:
    if settings.env == "production":
        return await _post_internal(
            "/internal/draft/intake-analysis", {"case_id": case_id}
        )

    if pool is None:
        raise RuntimeError("Database pool is not initialized in local mode")

    row = await pool.fetchrow(
        """
        SELECT analysis, transcript
        FROM public.case_intake_sessions
        WHERE case_id = $1 AND LOWER(status) = 'completed'
        ORDER BY id DESC
        LIMIT 1
        """,
        case_id,
    )

    if not row:
        return {"analysis": None, "transcript": None}

    return {
        "analysis": row.get("analysis"),
        "transcript": row.get("transcript"),
    }


async def get_case_documents(
    case_id: int, user_id: int, pool, advocate_id: int | None = None
) -> dict[str, list[dict[str, Any]]]:
    if settings.env == "production":
        if advocate_id is None:
            raise RuntimeError("advocate_id is required for production document access")
        data = await _post_internal(
            "/internal/draft/documents",
            {"case_id": case_id, "user_id": user_id, "advocate_id": advocate_id},
        )
        return {
            "case_documents": data.get("case_documents", []),
            "client_documents": data.get("client_documents", []),
        }

    if pool is None:
        raise RuntimeError("Database pool is not initialized in local mode")

    case_rows = await pool.fetch(
        """
        SELECT id, doc_type, file_url, status, extracted_text, extraction_status, created_at, updated_at,
               'case'::text AS source
        FROM public.case_documents
        WHERE case_id = $1
        """,
        case_id,
    )
    client_rows = await pool.fetch(
        """
        SELECT id, doc_type, file_url, status, extracted_text, extraction_status, created_at, updated_at,
               'client'::text AS source
        FROM public.client_documents
        WHERE user_id = $1
        """,
        user_id,
    )

    return {
        "case_documents": [dict(row) for row in case_rows],
        "client_documents": [dict(row) for row in client_rows],
    }


async def save_draft_session(
    case_id: int,
    document_type: str,
    generation_id: str,
    draft_json: dict[str, Any],
    advocate_id: int,
    pool,
) -> bool:
    if settings.env == "production":
        data = await _post_internal(
            "/internal/draft/save",
            {
                "case_id": case_id,
                "document_type": document_type,
                "generation_id": generation_id,
                "draft_json": draft_json,
                "advocate_id": advocate_id,
            },
        )
        return bool(data.get("saved", True))

    if pool is None:
        raise RuntimeError("Database pool is not initialized in local mode")

    result = await pool.execute(
        """
        INSERT INTO public.draft_sessions
            (case_id, document_type, generation_id, draft_json, advocate_id)
        VALUES ($1, $2, $3, $4::jsonb, $5)
        ON CONFLICT (generation_id) DO UPDATE
            SET case_id = EXCLUDED.case_id,
                document_type = EXCLUDED.document_type,
                draft_json = EXCLUDED.draft_json,
                advocate_id = EXCLUDED.advocate_id,
                updated_at = now()
        """,
        case_id,
        document_type,
        generation_id,
        json.dumps(draft_json),
        advocate_id,
    )
    logger.info("Draft saved (%s)", result)
    return True

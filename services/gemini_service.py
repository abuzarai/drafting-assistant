"""Gemini generation and section regeneration service."""

import asyncio
import json
import logging
import re
from uuid import uuid4

from google import genai

from config import settings
from models.schemas import DraftContent, DraftSection
from prompts.base import build_generation_prompt, build_regeneration_prompt
from prompts import (
    plaint,
    contract,
    written_statement,
    affidavit,
    appeal,
    notice,
    misc_petition,
    stay_injunction,
)

logger = logging.getLogger(__name__)

_model = None

DOCUMENT_INSTRUCTIONS = {
    "Plaint": plaint.INSTRUCTIONS,
    "Client-Lawyer Contract": contract.INSTRUCTIONS,
    "Written Statement": written_statement.INSTRUCTIONS,
    "Objection Response": written_statement.INSTRUCTIONS,
    "Affidavit": affidavit.INSTRUCTIONS,
    "Appeal Application": appeal.INSTRUCTIONS,
    "Notice": notice.INSTRUCTIONS,
    "Misc. Petition": misc_petition.INSTRUCTIONS,
    "Application (Stay/Injunction)": stay_injunction.INSTRUCTIONS,
}


def _extract_json(text: str) -> str:
    if not text:
        return "{}"

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return fenced.group(1).strip()

    first_obj = _extract_first_balanced_object(text)
    if first_obj:
        return first_obj

    return text.strip()


def _extract_first_balanced_object(text: str) -> str:
    if not text:
        return ""

    start = text.find("{")
    if start == -1:
        return ""

    in_string = False
    escaped = False
    depth = 0

    for i in range(start, len(text)):
        ch = text[i]

        if escaped:
            escaped = False
            continue

        if ch == "\\":
            escaped = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return ""


def _basic_json_sanitize(text: str) -> str:
    cleaned = str(text or "")
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return cleaned


async def _load_json_with_repair(
    model_ctx, raw_text: str, expected_shape_hint: str
) -> dict:
    candidate = _extract_json(raw_text)
    candidate = _basic_json_sanitize(candidate)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as first_error:
        logger.warning(
            "Initial JSON parse failed (%s). Attempting repair.", first_error
        )

    repair_prompt = f"""You are a strict JSON formatter.
Return ONLY valid minified JSON object (no markdown, no commentary).
Expected shape: {expected_shape_hint}

Input:
{candidate}
"""

    repaired = await asyncio.to_thread(
        model_ctx["client"].models.generate_content,
        model=model_ctx["model"],
        contents=repair_prompt,
        config=genai.types.GenerateContentConfig(temperature=0.0),
    )
    repaired_text = _basic_json_sanitize(_extract_json(repaired.text or ""))
    if not repaired_text.strip():
        raise ValueError("JSON repair returned empty content")
    return json.loads(repaired_text)


def _fallback_draft_payload(raw_text: str, document_type: str) -> dict:
    text = str(raw_text or "").strip()
    if not text:
        text = (
            "Draft content could not be parsed from model response. Please regenerate."
        )

    return {
        "title": f"{document_type} Draft",
        "sections": [
            {
                "id": "sec_1",
                "heading": "Draft Body",
                "content": text,
            }
        ],
    }


def _fallback_section_payload(
    raw_text: str, heading: str, current_content: str
) -> dict:
    text = str(raw_text or "").strip() or str(current_content or "").strip()
    if not text:
        text = "Section could not be regenerated from model response."
    return {"heading": heading, "content": text}


def get_model():
    global _model
    if _model is None:
        if not settings.gcp_project_id:
            raise RuntimeError("Missing GCP_PROJECT_ID for Vertex AI Gemini")
        _model = {
            "client": genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.google_vertex_location,
            ),
            "model": "gemini-2.5-flash",
        }
    return _model


async def generate_draft(
    case_context: dict,
    document_type: str,
    advocate_notes: str,
    language: str,
    rag_context: str = "",
) -> tuple[DraftContent, str]:
    model = get_model()
    client = model["client"]
    model_name = model["model"]
    prefilled = case_context.get("prefilled_fields", {})

    prompt = build_generation_prompt(
        document_type=document_type,
        language=language,
        title=str(case_context.get("title", "")),
        balanced_case_context=str(case_context.get("balanced_case_context") or ""),
        plaintiff=str(prefilled.get("plaintiff") or "To be specified"),
        defendant=str(prefilled.get("defendant") or "To be specified"),
        advocate=str(
            prefilled.get("advocate")
            or case_context.get("advocate_name")
            or "To be specified"
        ),
        advocate_email=str(
            prefilled.get("advocate_email") or case_context.get("advocate_email") or ""
        ),
        advocate_phone=str(
            prefilled.get("advocate_phone") or case_context.get("advocate_phone") or ""
        ),
        advocate_bar_council_id=str(
            prefilled.get("advocate_bar_council_id")
            or case_context.get("advocate_bar_council_id")
            or ""
        ),
        nature_of_dispute=str(prefilled.get("nature_of_dispute") or "To be specified"),
        key_facts=str(prefilled.get("key_facts") or ""),
        relief_sought=str(prefilled.get("relief_sought") or ""),
        jurisdiction=str(prefilled.get("jurisdiction") or ""),
        rag_context=rag_context,
        document_context=str(case_context.get("document_context") or ""),
        advocate_notes=advocate_notes,
        document_instructions=DOCUMENT_INSTRUCTIONS.get(document_type, ""),
    )

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model_name,
        contents=prompt,
        config=genai.types.GenerateContentConfig(temperature=0.2),
    )
    raw_text = response.text or ""
    try:
        parsed = await _load_json_with_repair(
            model,
            raw_text,
            '{"title":"string","sections":[{"id":"sec_1","heading":"string","content":"string"}]}',
        )
    except Exception as parse_error:
        logger.warning(
            "Draft JSON parse failed; using fallback payload (%s)", parse_error
        )
        parsed = _fallback_draft_payload(raw_text, document_type)

    draft = DraftContent.model_validate(parsed)
    generation_id = f"gen_{uuid4().hex[:12]}"
    return draft, generation_id


async def regenerate_section(
    section_id: str,
    instruction: str,
    current_draft: DraftContent,
    case_context: dict,
    document_type: str,
    language: str = "English",
) -> DraftSection:
    model = get_model()
    client = model["client"]
    model_name = model["model"]

    target = next((s for s in current_draft.sections if s.id == section_id), None)
    if target is None:
        raise ValueError(f"Section {section_id} not found")

    prefilled = case_context.get("prefilled_fields", {})
    prompt = build_regeneration_prompt(
        document_type=document_type,
        language=language,
        section_heading=target.heading,
        current_content=target.content,
        instruction=instruction,
        case_title=str(case_context.get("title", "")),
        plaintiff=str(prefilled.get("plaintiff") or "To be specified"),
        defendant=str(prefilled.get("defendant") or "To be specified"),
        nature_of_dispute=str(prefilled.get("nature_of_dispute") or "To be specified"),
    )

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model_name,
        contents=prompt,
        config=genai.types.GenerateContentConfig(temperature=0.2),
    )
    raw_text = response.text or ""
    try:
        payload = await _load_json_with_repair(
            model,
            raw_text,
            '{"heading":"string","content":"string"}',
        )
    except Exception as parse_error:
        logger.warning(
            "Section JSON parse failed; using fallback payload (%s)", parse_error
        )
        payload = _fallback_section_payload(raw_text, target.heading, target.content)

    return DraftSection(
        id=section_id,
        heading=str(payload.get("heading", target.heading)),
        content=str(payload.get("content", target.content)),
    )

"""Drafting routes."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from db.connection import get_pool
from models.schemas import (
    DraftExportRequest,
    DraftGenerateRequest,
    DraftGenerateResponse,
    DraftInitRequest,
    DraftInitResponse,
    DraftSaveRequest,
    DraftSaveResponse,
    RegenerateSectionRequest,
    RegenerateSectionResponse,
)
from services import context_service, export_service, gemini_service, rag_service
from services.draft_jobs import jobs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/draft", tags=["draft"])


def _http_from_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, LookupError):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))


@router.post("/init", response_model=DraftInitResponse)
async def draft_init(req: DraftInitRequest):
    pool = get_pool()
    try:
        case_context = await context_service.get_case_context(
            req.case_id, req.advocate_id, pool
        )
        intake = await context_service.get_intake_analysis(req.case_id, pool)
        documents = await context_service.get_case_documents(
            req.case_id, case_context.get("user_id"), pool, req.advocate_id
        )
    except Exception as error:
        raise _http_from_error(error)

    document_type = context_service.get_document_type(case_context.get("current_stage"))
    prefilled_fields = context_service.build_prefilled_fields(
        intake.get("analysis"), intake.get("transcript"), case_context
    )
    missing_documents = context_service.get_missing_documents(
        document_type,
        documents.get("case_documents", []),
        documents.get("client_documents", []),
    )

    return DraftInitResponse(
        case_id=req.case_id,
        current_stage=case_context.get("current_stage"),
        document_type=document_type,
        client_name=case_context.get("name") or "Unknown",
        language=case_context.get("language") or "English",
        prefilled_fields=prefilled_fields,
        missing_documents=missing_documents,
    )


async def _execute_generate(req: DraftGenerateRequest) -> DraftGenerateResponse:
    """The expensive part of generation, run as a background job."""
    pool = get_pool()
    try:
        case_context = await context_service.get_case_context(
            req.case_id, req.advocate_id, pool
        )
    except PermissionError:
        raise HTTPException(
            status_code=403, detail="Advocate not authorized for this case"
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Case not found")
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    try:
        intake = await context_service.get_intake_analysis(req.case_id, pool)
        documents = await context_service.get_case_documents(
            req.case_id, case_context.get("user_id"), pool, req.advocate_id
        )
        prefilled = context_service.build_prefilled_fields(
            intake.get("analysis"), intake.get("transcript"), case_context
        )
        document_context = context_service.build_document_context(
            documents.get("case_documents", []),
            documents.get("client_documents", []),
            req.document_type,
        )
        balanced_case_context = context_service.build_balanced_case_context(
            case_context,
            req.document_type,
            prefilled,
        )
        generation_context = {
            **case_context,
            "prefilled_fields": prefilled.model_dump(),
            "document_context": document_context,
            "balanced_case_context": balanced_case_context,
        }
        nature_of_dispute = prefilled.nature_of_dispute or ""
        rag_context = await rag_service.query_legal_references(
            f"{req.document_type} {nature_of_dispute} Pakistan law"
        )
        draft, generation_id = await gemini_service.generate_draft(
            case_context=generation_context,
            document_type=req.document_type,
            advocate_notes=req.advocate_notes,
            language=req.language,
            rag_context=rag_context,
        )
    except Exception as error:
        logger.exception("Draft generation failed")
        raise HTTPException(status_code=500, detail=f"Draft generation failed: {error}")

    return DraftGenerateResponse(
        document_type=req.document_type,
        draft=draft,
        legal_references_used=[],
        generation_id=generation_id,
    )


@router.post("/generate", status_code=202)
async def draft_generate(req: DraftGenerateRequest):
    """Queue generation as a background job; poll GET /draft/generate/{id}."""
    job_id = jobs.create(lambda: _execute_generate(req))
    return {"job_id": job_id, "status": "queued"}


@router.get("/generate/{job_id}")
async def draft_generate_status(job_id: str):
    """Job status for a queued generation."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    payload = {"job_id": job_id, "status": job["status"]}
    if job["status"] == "succeeded":
        payload["result"] = job["result"]
    elif job["status"] == "failed":
        payload["error"] = job["error"]
    return payload


@router.post("/regenerate-section", response_model=RegenerateSectionResponse)
async def regenerate_section(req: RegenerateSectionRequest):
    if not any(section.id == req.section_id for section in req.current_draft.sections):
        raise HTTPException(
            status_code=404, detail=f"Section {req.section_id} not found"
        )

    pool = get_pool()
    try:
        case_context = await context_service.get_case_context(
            req.case_id, req.advocate_id, pool
        )
        intake = await context_service.get_intake_analysis(req.case_id, pool)
        documents = await context_service.get_case_documents(
            req.case_id, case_context.get("user_id"), pool, req.advocate_id
        )
        prefilled = context_service.build_prefilled_fields(
            intake.get("analysis"), intake.get("transcript"), case_context
        )
        document_context = context_service.build_document_context(
            documents.get("case_documents", []),
            documents.get("client_documents", []),
            req.document_type,
        )
        balanced_case_context = context_service.build_balanced_case_context(
            case_context,
            req.document_type,
            prefilled,
        )
        generation_context = {
            **case_context,
            "prefilled_fields": prefilled.model_dump(),
            "document_context": document_context,
            "balanced_case_context": balanced_case_context,
        }
        section = await gemini_service.regenerate_section(
            section_id=req.section_id,
            instruction=req.instruction,
            current_draft=req.current_draft,
            case_context=generation_context,
            document_type=req.document_type,
            language=req.language,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except Exception as error:
        logger.exception("Section regeneration failed")
        raise HTTPException(
            status_code=500, detail=f"Section regeneration failed: {error}"
        )

    return RegenerateSectionResponse(
        section_id=section.id,
        heading=section.heading,
        content=section.content,
    )


@router.post("/save", response_model=DraftSaveResponse)
async def draft_save(req: DraftSaveRequest):
    pool = get_pool()
    try:
        saved = await context_service.save_draft_session(
            case_id=req.case_id,
            document_type=req.document_type,
            generation_id=req.generation_id,
            draft_json=req.draft.model_dump(),
            advocate_id=req.advocate_id,
            pool=pool,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Draft save failed: {error}")

    return DraftSaveResponse(generation_id=req.generation_id, saved=saved)


@router.post("/export")
async def draft_export(req: DraftExportRequest):
    if req.format.lower() != "docx":
        raise HTTPException(status_code=422, detail="Only docx export is supported")

    buffer = export_service.generate_docx(req.final_draft, req.document_type)
    filename = f"{req.document_type}_{req.case_id}.docx".replace(" ", "_")

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

"""Pydantic schemas for drafting endpoints."""

from typing import Optional

from pydantic import BaseModel


class DraftSection(BaseModel):
    id: str
    heading: str
    content: str


class DraftContent(BaseModel):
    title: str
    sections: list[DraftSection]


class PrefilledFields(BaseModel):
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    advocate: Optional[str] = None
    advocate_email: Optional[str] = None
    advocate_phone: Optional[str] = None
    advocate_bar_council_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    nature_of_dispute: Optional[str] = None
    relief_sought: Optional[str] = None
    key_facts: Optional[str] = None


class DraftInitRequest(BaseModel):
    case_id: int
    advocate_id: int


class DraftGenerateRequest(BaseModel):
    case_id: int
    advocate_id: int
    document_type: str
    advocate_notes: str = ""
    language: str = "English"


class RegenerateSectionRequest(BaseModel):
    generation_id: str
    section_id: str
    instruction: str
    current_draft: DraftContent
    case_id: int
    advocate_id: int
    document_type: str
    language: str = "English"


class DraftSaveRequest(BaseModel):
    case_id: int
    document_type: str
    generation_id: str
    advocate_id: int
    draft: DraftContent


class DraftExportRequest(BaseModel):
    case_id: int
    document_type: str
    final_draft: DraftContent
    format: str = "docx"


class DraftInitResponse(BaseModel):
    case_id: int
    current_stage: Optional[str]
    document_type: str
    client_name: str
    language: str
    prefilled_fields: PrefilledFields
    missing_documents: list[str]


class DraftGenerateResponse(BaseModel):
    document_type: str
    draft: DraftContent
    legal_references_used: list[str]
    generation_id: str


class RegenerateSectionResponse(BaseModel):
    section_id: str
    heading: str
    content: str


class DraftSaveResponse(BaseModel):
    generation_id: str
    saved: bool


class DraftExportResponse(BaseModel):
    message: str

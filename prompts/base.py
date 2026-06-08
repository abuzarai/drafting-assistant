"""Shared prompt builders."""


def build_generation_prompt(
    document_type: str,
    language: str,
    title: str,
    balanced_case_context: str,
    plaintiff: str,
    defendant: str,
    advocate: str,
    advocate_email: str,
    advocate_phone: str,
    advocate_bar_council_id: str,
    nature_of_dispute: str,
    key_facts: str,
    relief_sought: str,
    jurisdiction: str,
    rag_context: str,
    document_context: str,
    advocate_notes: str,
    document_instructions: str,
) -> str:
    return f"""You are a legal drafting assistant for Pakistani civil courts.
Draft a formal {document_type} following Pakistani legal
conventions and standard court formatting.
Language: {language}. Use formal legal language throughout.

{document_instructions}

CASE CONTEXT:
Case Title: {title}
Balanced Context (use selectively, only when clause-relevant):
{balanced_case_context}
Plaintiff: {plaintiff}
Defendant: {defendant}
Advocate: {advocate}
Advocate Email: {advocate_email}
Advocate Phone: {advocate_phone}
Advocate Bar Council ID: {advocate_bar_council_id}
Nature of Dispute: {nature_of_dispute}
Key Facts: {key_facts}
Relief Sought: {relief_sought}
Jurisdiction: {jurisdiction}

LEGAL REFERENCES:
{rag_context if rag_context else "No external references provided."}

VERIFIED CASE DOCUMENTS:
{document_context if document_context else "No verified documents available."}

ADVOCATE INSTRUCTIONS:
{advocate_notes if advocate_notes else "None provided."}

OUTPUT FORMAT:
Return ONLY a valid JSON object. No markdown. No preamble.
{{
  "title": "court heading string",
  "sections": [
    {{"id": "sec_1", "heading": "Section Name", "content": "Full section text"}}
  ]
}}

IMPORTANT WRITING RULES:
- Use only context that is directly relevant to the draft type and section.
- Do not force every available detail into the draft.
- Avoid repeating identity details outside sections where legally needed.
- Never invent facts, identities, numbers, addresses, dates, or legal outcomes.
- If a material detail is missing, use neutral placeholders such as "To be specified".
"""


def build_regeneration_prompt(
    document_type: str,
    language: str,
    section_heading: str,
    current_content: str,
    instruction: str,
    case_title: str,
    plaintiff: str,
    defendant: str,
    nature_of_dispute: str,
) -> str:
    return f"""You are a legal drafting assistant for Pakistani civil courts.
Rewrite one section of a {document_type}.
Language: {language}. Use formal legal language.

CASE CONTEXT:
Case Title: {case_title}
Plaintiff: {plaintiff}
Defendant: {defendant}
Nature of Dispute: {nature_of_dispute}

SECTION TO REWRITE:
Heading: {section_heading}
Content:
{current_content}

REVISION INSTRUCTION:
{instruction}

OUTPUT FORMAT:
Return ONLY a valid JSON object. No markdown.
{{
  "heading": "{section_heading}",
  "content": "Rewritten full section text"
}}
"""

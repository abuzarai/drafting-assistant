# AI Document Drafting Service

> Final Year Project, AI microservice · Part of the [Insafdaar](https://github.com/abuzarai/insafdaar-webapp) legal case management platform.  
> FastAPI microservice that generates, iterates, and exports legal documents for Pakistani courts using Gemini AI.

[![License](https://img.shields.io/badge/License-PolyForm_Noncommercial-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/flash/)

---

## What Is This?

This microservice generates plaints, written statements, affidavits, appeals, contracts, notices, petitions, and injunctions for Pakistani courts, using case data and the Gemini API (gemini-2.5-flash).

It powers the **AI Document Drafting** feature inside the main Insafdaar webapp. Advocates can generate full drafts, regenerate specific sections with custom instructions, and export the result as a DOCX file from the case dashboard.

---

## Architecture

```
Express Backend (via internal API)
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│                  DRAFTING SERVICE (:8080)                 │
│                                                          │
│  ┌──────────── ENV=local ───────────────────────────┐    │
│  │  Direct asyncpg to PostgreSQL for case data      │    │
│  └──────────────────────────────────────────────────┘    │
│  ┌──────── ENV=production ───────────────────────────┐   │
│  │  HTTP proxy to Express /internal/draft/* endpoints │   │
│  │  with X-Internal-Key auth                         │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌───────────────── GENERATION PIPELINE ───────────────┐ │
│  │                                                    │ │
│  │  1. Case Context (SQL join or Express proxy)       │ │
│  │     - client_cases, users, client_profiles,        │ │
│  │       advocate_profiles tables                     │ │
│  │                                                    │ │
│  │  2. Intake Analysis (case_intake_sessions)         │ │
│  │     - JSONB analysis: parties, locations,          │ │
│  │       dates, amounts, issue summary                │ │
│  │     - Full transcript from voice interview         │ │
│  │                                                    │ │
│  │  3. Case & Client Documents                        │ │
│  │     - Filtered by document type relevance          │ │
│  │     - Truncated by token budget per doc type       │ │
│  │                                                    │ │
│  │  4. Prefilled Fields from analysis entities        │ │
│  │                                                    │ │
│  │  5. Balanced Case Context (type-specific fields)   │ │
│  │                                                    │ │
│  │  6. RAG Legal References (Phase 2, stub)          │ │
│  │                                                    │ │
│  │  7. Gemini 2.5 Flash (temperature=0.2)             │ │
│  │     - Document-type-specific prompt instructions   │ │
│  │     - JSON output with sections + headings + body  │ │
│  │     - Multi-layer repair on malformed JSON         │ │
│  │                                                    │ │
│  │  8. DOCX Export (python-docx)                      │ │
│  │     - A4, Times New Roman 12pt, justified          │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

<details>
<summary>API Reference</summary>

All endpoints are under the `/draft` prefix.

### `POST /draft/init`

Initialise a drafting session: detect document type, prefilled fields, and missing documents.

**Request:**
```json
{
  "case_id": 44,
  "advocate_id": 12
}
```

**Response:**
```json
{
  "case_id": 44,
  "current_stage": "case_active",
  "document_type": "Plaint",
  "client_name": "Abuzar Khan",
  "language": "English",
  "prefilled_fields": {
    "plaintiff": "Abuzar Khan",
    "defendant": "To be specified",
    "advocate": "Ali Ahmed",
    "advocate_email": "ali@example.com",
    "advocate_phone": "+92-300-1234567",
    "advocate_bar_council_id": "KHC-1234",
    "jurisdiction": "Civil Judge, Lahore",
    "nature_of_dispute": "Property boundary dispute",
    "relief_sought": "Declaration and permanent injunction",
    "key_facts": "Locations: Lahore | Dates: 2022"
  },
  "missing_documents": ["CNIC_FRONT", "FIR_COPY"]
}
```

### `POST /draft/generate`

Generate a full legal document draft using Gemini.

**Request:**
```json
{
  "case_id": 44,
  "advocate_id": 12,
  "document_type": "Plaint",
  "advocate_notes": "Emphasize the property boundary dispute.",
  "language": "English"
}
```

**Response:**
```json
{
  "document_type": "Plaint",
  "draft": {
    "title": "IN THE COURT OF CIVIL JUDGE, LAHORE",
    "sections": [
      { "id": "sec_1", "heading": "Parties to the Suit", "content": "..." },
      { "id": "sec_2", "heading": "Facts of the Case", "content": "..." },
      { "id": "sec_3", "heading": "Cause of Action", "content": "..." },
      { "id": "sec_4", "heading": "Relief Sought", "content": "..." },
      { "id": "sec_5", "heading": "Verification", "content": "..." }
    ]
  },
  "legal_references_used": [],
  "generation_id": "gen_abc123def456"
}
```

### `POST /draft/regenerate-section`

Regenerate a single section with specific instructions (e.g., "make this more concise", "focus on X").

**Request:**
```json
{
  "case_id": 44,
  "advocate_id": 12,
  "generation_id": "gen_abc123def456",
  "section_id": "sec_2",
  "instruction": "Make this more concise, focus on 2022 events only.",
  "document_type": "Plaint",
  "language": "English",
  "current_draft": {
    "title": "...",
    "sections": [
      { "id": "sec_1", "heading": "...", "content": "..." },
      { "id": "sec_2", "heading": "Facts of the Case", "content": "..." }
    ]
  }
}
```

**Response:**
```json
{
  "section_id": "sec_2",
  "heading": "Facts of the Case",
  "content": "... revised content ..."
}
```

### `POST /draft/save`

Persist the current draft to the database.

**Request:**
```json
{
  "case_id": 44,
  "document_type": "Plaint",
  "generation_id": "gen_abc123def456",
  "advocate_id": 12,
  "draft": { "title": "...", "sections": [...] }
}
```

**Response:** `{ "generation_id": "gen_abc123def456", "saved": true }`

### `POST /draft/export`

Export the final draft as a formatted DOCX file.

**Request:**
```json
{
  "case_id": 44,
  "document_type": "Plaint",
  "final_draft": { "title": "...", "sections": [...] },
  "format": "docx"
}
```

**Response:** Binary DOCX file stream (`Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`)

### `GET /health`

**Response:** `{"status": "ok", "env": "local", "service": "drafting-assistant"}`

</details>

---

## Document Types

The service generates 9 document types, each with stage-triggered defaults and required sections:

| Document Type | Trigger Stage | Required Sections |
|---------------|---------------|-------------------|
| **Plaint** | `case_active`, `filing` | Parties, Jurisdiction, Facts, Cause of Action, Relief Sought, Verification |
| **Written Statement** | `response_stage` | Preliminary Objections, Para-wise Reply, Affirmative Defenses, Prayer |
| **Objection Response** | `maintainability` | (same as Written Statement) |
| **Affidavit** | `evidence_stage` | Deponent Details, Statement of Facts, Verification, Attestation |
| **Appeal** | `appeal` | Parties, Impugned Order, Grounds of Appeal, Prayer |
| **Client-Lawyer Contract** | `pre_acceptance` | Parties, Recitals, Scope, Fee Structure, Payment, Obligations, Confidentiality, Conflict, Term, Liability, Dispute Resolution, Governing Law, Signature Blocks |
| **Notice** | *(manual)* | Addressee, Subject, Authority, Facts, Breach, Demand, Consequences, Signature |
| **Misc. Petition** | *(manual)* | Cause Title, Background Facts, Grounds, Interim Relief, Prayer, Verification |
| **Stay/Injunction** | *(manual)* | Cause Title, Facts, Grounds for Interim Relief, Urgency & Irreparable Loss, Balance of Convenience, Prayer |

### Document Context Limits

Each document type has configurable limits to stay within token budgets:

| Document Type | Max Docs | Max Chars/Doc | Max Total Chars |
|---------------|----------|---------------|-----------------|
| Client-Lawyer Contract | 5 | 1,100 | 4,500 |
| Affidavit | 5 | 1,200 | 4,800 |
| Notice | 5 | 1,200 | 4,800 |
| Misc. Petition | 6 | 1,300 | 5,600 |
| Stay/Injunction | 6 | 1,400 | 6,000 |
| All others | 6 | 1,400 | 6,200 |

---

## Generation Pipeline (Detailed)

When `/draft/generate` is called, the service assembles a rich context for Gemini:

1. **Case Context**: Joined data from `client_cases`, `users`, `client_profiles`, `advocate_profiles`. Includes case title, stage, legal domain, parties, verification status.

2. **Intake Analysis**: The latest voice interview's structured analysis (JSONB) and transcript. Extracted by `build_prefilled_fields()`: plaintiff/defendant names, advocate details, jurisdiction, nature of dispute, relief sought, key facts (dates, locations, amounts).

3. **Verified Documents**: `case_documents` and `client_documents` with `status = 'approved'` and non-empty `extracted_text`. Filtered by relevance to target document type, capped by per-type token budgets.

4. **Balanced Case Context**: A compact, type-specific summary. Contracts include payment terms and contact details; other documents include nature of dispute and key facts.

5. **Legal References**: Optional RAG assistant citations (Phase 2, currently stubbed).

6. **Prompt Construction**: The base prompt (`prompts/base.py`) combines:
   - System role ("legal drafting assistant for Pakistani civil courts")
   - Document-specific instructions from `prompts/{type}.py`
   - All context layers above
   - Advocate's custom notes
   - Strict JSON output specification
   - Writing rules (use only relevant context, no invented facts, "To be specified" for gaps)

7. **Gemini Invocation**: `temperature=0.2` for consistent output. If JSON parsing fails, a second repair call with `temperature=0.0` attempts to fix it. If that also fails, a fallback payload is returned.

8. **DOCX Export**: `python-docx` generates A4, Times New Roman 12pt, justified alignment, with title as Heading 1 and sections as Heading 2.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | FastAPI + Uvicorn |
| **AI Model** | Gemini 2.5 Flash via the Gemini API (`temperature=0.2`) |
| **Database** | asyncpg (PostgreSQL connection pool, local mode) |
| **Export** | python-docx (A4, Times New Roman 12pt) |
| **Config** | pydantic-settings + python-dotenv |
| **Deployment** | Container in the Insafdaar compose stack (Oracle Cloud Infrastructure) |
| **Language** | Python 3.11 |

---

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (local mode only)
- Gemini API key ([AI Studio](https://aistudio.google.com/apikey))

### Setup

```bash
# Clone
git clone https://github.com/abuzarai/drafting-assistant.git
cd drafting-assistant

# Install dependencies from the locked graph (pyproject.toml + uv.lock)
uv sync

# Environment
cp .env.example .env
# Edit .env with your values
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENV` | Yes | `local` | Runtime mode: `local` or `production` |
| `GEMINI_API_KEY` | Yes | None | Gemini API key (takes precedence over legacy Vertex settings) |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Gemini model name |
| `DB_HOST` | Local only | `localhost` | PostgreSQL host |
| `DB_PORT` | Local only | `5432` | PostgreSQL port |
| `DB_DATABASE` | Local only | `insafdaar_db` | PostgreSQL database |
| `DB_USER` | Local only | `postgres` | PostgreSQL user |
| `DB_PASSWORD` | Local only | None | PostgreSQL password |
| `EXPRESS_INTERNAL_URL` | Prod only | None | Express backend internal URL |
| `INTERNAL_API_KEY` | Prod only | None | Shared secret for internal auth |
| `RAG_API_URL` | No | None | Legal RAG Assistant URL (Phase 2) |
| `PORT` | No | `8080` | Service port |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated CORS origins |

### Run

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Health check: `curl http://localhost:8080/health`

### Test

```bash
uv run pytest tests/test_draft_api.py -v
```

---

## Docker

```bash
docker build -t drafting-assistant .
docker run --rm -p 8080:8080 --env-file .env drafting-assistant
```

---

## Deployment

- **Platform**: container in the Insafdaar compose stack (Oracle Cloud Infrastructure)
- **Mode**: `ENV=production` (proxies DB queries to the Express backend via `/internal/draft/*`; no direct PostgreSQL connection)
- **Auth**: the Express backend's `/internal/draft/*` endpoints require the shared `X-Internal-Key`
- **Deploys**: handled by the main webapp's pipeline (GitHub Actions builds the image on a runner, ships it, and applies the stack)

---

## Repository Structure

```
drafting-assistant/
├── main.py                    # FastAPI entrypoint, CORS, health
├── config.py                  # Pydantic settings (all env vars)
├── db/
│   └── connection.py          # asyncpg pool setup
├── models/
│   └── schemas.py             # Pydantic request/response models
├── routes/
│   └── draft.py               # init, generate, regenerate, save, export
├── services/
│   ├── gemini_service.py      # Gemini invocation, JSON parsing, repair fallback
│   ├── context_service.py     # Case context, intake analysis, document assembly
│   ├── export_service.py      # DOCX generation (python-docx)
│   └── rag_service.py         # RAG client (Phase 2 stub)
├── prompts/
│   ├── base.py                # System prompt builder + JSON output spec
│   ├── plaint.py              # Plaint document instructions
│   ├── written_statement.py   # Written Statement & Objection Response
│   ├── affidavit.py           # Affidavit instructions
│   ├── appeal.py              # Appeal instructions
│   ├── contract.py            # Client-Lawyer Contract (15 sections)
│   ├── notice.py              # Legal Notice instructions
│   ├── misc_petition.py       # Misc. Petition instructions
│   └── stay_injunction.py     # Stay/Injunction instructions
├── tests/
│   └── test_draft_api.py      # FastAPI TestClient test suite
├── Dockerfile                 # Container build
├── pyproject.toml             # Dependencies & project metadata
└── uv.lock                    # Locked dependency graph
```

---

## License

Licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use requires written permission from the author.
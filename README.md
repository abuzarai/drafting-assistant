# AI Document Drafting Service

> **Final Year Project — AI Microservice** · Part of the [Insafdaar](https://github.com/abuzarai/insafdaar-webapp) legal case management platform.  
> FastAPI microservice that generates, iterates, and exports legal documents for Pakistani courts using Gemini AI.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.0_Flash-4285F4?logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/flash/)

---

## 📖 What Is This?

This microservice generates complete legal documents (plaints, affidavits, written statements, appeals, contracts, and more) from case data using Gemini 2.0 Flash via Vertex AI. Advocates can generate, regenerate specific sections with custom instructions, and export drafts as DOCX files.

It is called by the Express backend in the main Insafdaar webapp and enriches Gemini prompts with case context, intake analysis, verified documents, and optional RAG-based legal references.

---

## 🏗️ Architecture

```
Express Backend (via internal API)
     │
     ▼
Drafting Service
     │
     ├── Gemini 2.0 Flash (document generation)
     ├── PostgreSQL (local mode) or Express API (production)
     └── Legal RAG Assistant (optional legal references)
     │
     ▼
DOCX Export
```

### Two Deployment Modes

| Mode | DB Access | Use Case |
|------|-----------|----------|
| `ENV=local` | Direct asyncpg to PostgreSQL | Local development |
| `ENV=production` | Calls Express `/internal/draft/*` endpoints | Cloud Run (no cross-cloud DB) |

---

## 📄 Supported Document Types

| Stage | Document Type |
|-------|---------------|
| Pre-acceptance | Client-Lawyer Contract |
| Case Active / Filing | Plaint |
| Response Stage | Written Statement |
| Maintainability | Objection Response |
| Evidence Stage | Affidavit |
| Appeal | Appeal Application |
| *(unmapped)* | Notice, Misc. Petition, Stay/Injunction |

---

## 🔌 API Endpoints

All under `/draft`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/draft/init` | Prefill fields, detect missing docs, identify document type |
| POST | `/draft/generate` | Full Gemini-powered draft generation |
| POST | `/draft/regenerate-section` | Rewrite one section with advocate instructions |
| POST | `/draft/save` | Persist current draft |
| POST | `/draft/export` | Generate and download DOCX |
| GET | `/health` | Health check |

---

## 🚀 Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (local mode only)
- Vertex AI access in your GCP project

### Setup

```bash
# Clone
git clone https://github.com/abuzarai/drafting-assistant.git
cd drafting-assistant

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env with your values
```

### Run

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Health check: `curl http://localhost:8001/health`

---

## 🐳 Docker

```bash
docker build -t drafting-assistant .
docker run --rm -p 8080:8080 --env-file .env drafting-assistant
```

---

## 📝 License

Licensed under the [Apache License 2.0](LICENSE).  

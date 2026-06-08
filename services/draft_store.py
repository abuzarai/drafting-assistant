"""Draft store — PostgreSQL-backed persistence for draft sessions.

Replaces in-memory generation store. Cloud Run scales to zero and runs
multiple instances, so in-memory state is unreliable.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.draft_sessions (
    id BIGSERIAL PRIMARY KEY,
    generation_id TEXT UNIQUE NOT NULL,
    case_id INTEGER NOT NULL,
    advocate_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    draft_json JSONB NOT NULL,
    case_context_json JSONB,
    advocate_notes TEXT DEFAULT '',
    language TEXT DEFAULT 'English',
    status TEXT DEFAULT 'DRAFT' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_draft_sessions_case_doctype
    ON public.draft_sessions (case_id, document_type, updated_at DESC);
"""


async def ensure_table(pool: asyncpg.Pool) -> None:
    """Create the draft_sessions table if it doesn't exist. Called on startup."""
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLE_SQL)
        await conn.execute(CREATE_INDEX_SQL)
    logger.info("draft_sessions table ensured")


async def save_draft(
    pool: asyncpg.Pool,
    generation_id: str,
    case_id: int,
    advocate_id: int,
    document_type: str,
    draft_json: dict[str, Any],
    case_context_json: Optional[dict[str, Any]] = None,
    advocate_notes: str = "",
    language: str = "English",
) -> None:
    """Insert or update a draft session."""
    await pool.execute(
        """
        INSERT INTO public.draft_sessions
            (generation_id, case_id, advocate_id, document_type,
             draft_json, case_context_json, advocate_notes, language)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
        ON CONFLICT (generation_id) DO UPDATE SET
            draft_json = EXCLUDED.draft_json,
            case_context_json = COALESCE(EXCLUDED.case_context_json, draft_sessions.case_context_json),
            advocate_notes = EXCLUDED.advocate_notes,
            language = EXCLUDED.language,
            updated_at = NOW()
        """,
        generation_id,
        case_id,
        advocate_id,
        document_type,
        json.dumps(draft_json),
        json.dumps(case_context_json) if case_context_json else None,
        advocate_notes,
        language,
    )
    logger.info(f"Draft saved: {generation_id} for case {case_id}")


async def get_draft(
    pool: asyncpg.Pool, generation_id: str
) -> Optional[dict[str, Any]]:
    """Fetch a draft session by generation_id."""
    row = await pool.fetchrow(
        """
        SELECT generation_id, case_id, advocate_id, document_type,
               draft_json, case_context_json, advocate_notes, language,
               status, created_at, updated_at
        FROM public.draft_sessions
        WHERE generation_id = $1
        """,
        generation_id,
    )
    if not row:
        return None

    result = dict(row)
    # Parse JSONB fields if they come back as strings
    for field in ("draft_json", "case_context_json"):
        val = result.get(field)
        if isinstance(val, str):
            try:
                result[field] = json.loads(val)
            except json.JSONDecodeError:
                pass
    return result


async def get_latest_draft(
    pool: asyncpg.Pool, case_id: int, document_type: str
) -> Optional[dict[str, Any]]:
    """Fetch the most recent draft for a case + document type."""
    row = await pool.fetchrow(
        """
        SELECT generation_id, case_id, advocate_id, document_type,
               draft_json, case_context_json, advocate_notes, language,
               status, created_at, updated_at
        FROM public.draft_sessions
        WHERE case_id = $1 AND document_type = $2
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        case_id, document_type,
    )
    if not row:
        return None

    result = dict(row)
    for field in ("draft_json", "case_context_json"):
        val = result.get(field)
        if isinstance(val, str):
            try:
                result[field] = json.loads(val)
            except json.JSONDecodeError:
                pass
    return result


async def update_draft_content(
    pool: asyncpg.Pool, generation_id: str, draft_json: dict[str, Any]
) -> bool:
    """Update only the draft content (e.g. after section regeneration)."""
    result = await pool.execute(
        """
        UPDATE public.draft_sessions
        SET draft_json = $1::jsonb, updated_at = NOW()
        WHERE generation_id = $2
        """,
        json.dumps(draft_json),
        generation_id,
    )
    updated = result == "UPDATE 1"
    if updated:
        logger.info(f"Draft content updated: {generation_id}")
    return updated


async def mark_exported(pool: asyncpg.Pool, generation_id: str) -> bool:
    """Mark a draft session as exported."""
    result = await pool.execute(
        """
        UPDATE public.draft_sessions
        SET status = 'EXPORTED', updated_at = NOW()
        WHERE generation_id = $1
        """,
        generation_id,
    )
    return result == "UPDATE 1"

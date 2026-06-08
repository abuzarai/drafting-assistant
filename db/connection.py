"""Database connection management for local mode."""

import logging

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

CREATE_DRAFT_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS public.draft_sessions (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    generation_id TEXT UNIQUE NOT NULL,
    draft_json JSONB NOT NULL,
    advocate_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
"""


async def init_pool() -> asyncpg.Pool | None:
    global _pool
    if settings.env != "local":
        logger.info("Skipping DB pool initialization in production mode")
        return None

    if _pool is not None:
        return _pool

    _pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_database,
        user=settings.db_user,
        password=settings.db_password,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )

    async with _pool.acquire() as conn:
        await conn.execute(CREATE_DRAFT_SESSIONS_SQL)

    logger.info("Local PostgreSQL pool initialized")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Local PostgreSQL pool closed")


def get_pool() -> asyncpg.Pool | None:
    if settings.env != "local":
        return None
    return _pool

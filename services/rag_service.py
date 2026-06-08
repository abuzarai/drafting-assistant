"""RAG service (Phase 1 stub)."""

import logging

logger = logging.getLogger(__name__)


async def query_legal_references(query: str, k: int = 5) -> str:
    logger.info("RAG stub called with query: %s (k=%s)", query, k)
    return ""

"""Bounded retry for Gemini transient errors (429 / 5xx).

Retrying a timeout is deliberately avoided: a timed-out generation may still
be running server-side, and retrying would duplicate the expensive call.
"""

import asyncio
import logging
import random

logger = logging.getLogger(__name__)

TRANSIENT_STATUSES = {429, 500, 502, 503}
DEFAULT_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 10.0
DEFAULT_TIMEOUT = 240  # generous: document generation can be slow


def transient_status_of(exc: BaseException):
    status = getattr(exc, "code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status", None)
    return int(status) if status else None


async def gemini_call_with_retry(
    coro_factory,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    timeout: float = DEFAULT_TIMEOUT,
):
    """Await coro_factory() with exponential backoff on transient statuses.

    The call is also bounded by asyncio.timeout, so a hung provider raises
    TimeoutError (not retried) instead of hanging the request forever.
    """
    for attempt in range(attempts):
        try:
            return await asyncio.wait_for(coro_factory(), timeout=timeout)
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            status = transient_status_of(exc)
            if status not in TRANSIENT_STATUSES or attempt == attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2**attempt)) * (0.5 + random.random())
            logger.warning(
                "Gemini transient %s; retrying in %.1fs (attempt %d/%d)",
                status,
                delay,
                attempt + 1,
                attempts,
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
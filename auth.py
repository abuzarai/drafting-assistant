"""Inbound auth for the drafting service (audit: unauthenticated Gemini spend).

`x-internal-key` must match settings.internal_api_key on every /draft/* route
when the key is configured (compose sets it in production). Bare local runs
without a key stay permissive so `env=local` direct-DB mode keeps working.
"""

import hmac

from fastapi import Header, HTTPException
from config import settings


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    expected = settings.internal_api_key
    if not expected:
        return
    if not hmac.compare_digest(x_internal_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid internal key")
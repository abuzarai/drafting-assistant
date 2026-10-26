"""Inbound auth for the drafting service (audit: unauthenticated Gemini spend).

`x-internal-key` must match settings.internal_api_key on every /draft/* route
in both local and production environments. Missing configuration fails closed.
"""

import hmac

from fastapi import Header, HTTPException
from config import settings


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    expected = settings.internal_api_key
    if not expected:
        raise HTTPException(status_code=503, detail="Drafting authentication is not configured")
    if not hmac.compare_digest(x_internal_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid internal key")
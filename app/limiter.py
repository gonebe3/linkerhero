from __future__ import annotations

import os
from flask_limiter import Limiter


def _rate_key() -> str:
    from flask import session, request
    uid = session.get("user_id")
    if uid:
        return f"user:{uid}"
    return request.headers.get("X-Forwarded-For", request.remote_addr)


limiter = Limiter(
    key_func=_rate_key,
    storage_uri=os.getenv("REDIS_URL", "memory://"),
    strategy="fixed-window",
    application_limits=[],
    default_limits=[],
    headers_enabled=True,
)

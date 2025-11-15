from __future__ import annotations

import os
from flask_limiter import Limiter


def _client_ip():
    from flask import request
    xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return xff or request.remote_addr


_ALLOWED_IPS = {ip.strip() for ip in (os.getenv("RATE_LIMIT_IP_ALLOWLIST") or "").split(",") if ip.strip()}


def _rate_key() -> str:
    from flask import session
    uid = session.get("user_id")
    if uid:
        return f"user:{uid}"
    return _client_ip()


limiter = Limiter(
    key_func=_rate_key,
    storage_uri=os.getenv("REDIS_URL", "memory://"),
    strategy="fixed-window",
    application_limits=[],
    default_limits=[],
    headers_enabled=True,
)


@limiter.request_filter
def _skip_limits() -> bool:
    try:
        return _client_ip() in _ALLOWED_IPS
    except Exception:
        return False

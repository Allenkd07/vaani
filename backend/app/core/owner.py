"""Anonymous ownership: each browser gets a random token in an HttpOnly cookie; records store only its hash."""

import hashlib
import re
import secrets

from fastapi import Request
from starlette.requests import HTTPConnection
from starlette.responses import Response

OWNER_COOKIE = "vaani_owner"
COOKIE_MAX_AGE_SEC = 365 * 24 * 3600
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")  # secrets.token_urlsafe(32)


def _valid_token(token: str | None) -> str | None:
    return token if token and _TOKEN_PATTERN.fullmatch(token) else None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def owner_id_from_cookie(connection: HTTPConnection) -> str | None:
    token = _valid_token(connection.cookies.get(OWNER_COOKIE))
    return hash_token(token) if token else None


async def ensure_owner_cookie(request: Request, call_next) -> Response:
    """HTTP middleware: issues the cookie on the first request (normally the page load)."""
    token = _valid_token(request.cookies.get(OWNER_COOKIE))
    issued = token is None
    if issued:
        token = secrets.token_urlsafe(32)
    request.state.owner_id = hash_token(token)

    response = await call_next(request)
    if issued:
        response.set_cookie(
            OWNER_COOKIE,
            token,
            max_age=COOKIE_MAX_AGE_SEC,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
    return response

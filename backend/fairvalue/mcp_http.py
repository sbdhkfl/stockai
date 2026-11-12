"""FAIRVALUE AI remote MCP transport — MCP Streamable HTTP.

Serves the SAME server instance as the stdio transport (`fairvalue.mcp_server`):
identical 11 tools, identical responses, shared in-memory report store. The
stdio transport is untouched and keeps working as before.

Run:  python -m fairvalue.mcp_http          (Streamable HTTP on :8001, path /mcp)

Auth (required by default): bearer token from FAIRVALUE_MCP_TOKEN, falling back
to FAIRVALUE_API_KEY, compared in constant time (same contract as the REST API;
`Authorization: Bearer <token>` or `X-API-Key: <token>`). The server refuses to
start without a token unless FAIRVALUE_MCP_ALLOW_ANON=1 (loopback development
only), and refuses a non-loopback bind without a token outright.
"""
from __future__ import annotations

import hmac
import os

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from fairvalue.mcp_server import mcp

MCP_PATH = "/mcp"
_LOOPBACK = ("127.0.0.1", "localhost", "::1")


def _expected_token() -> str | None:
    # resolved per request: tests/config changes need no re-import
    return os.environ.get("FAIRVALUE_MCP_TOKEN") or os.environ.get("FAIRVALUE_API_KEY")


def _anon_allowed() -> bool:
    return os.environ.get("FAIRVALUE_MCP_ALLOW_ANON") == "1"


def _supplied_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    return request.headers.get("x-api-key", "")


def _allowed(request: Request) -> bool:
    if _anon_allowed():
        return True
    expected = _expected_token()
    if not expected:
        return False  # fail closed: no token configured, no access
    supplied = _supplied_token(request)
    return bool(supplied) and hmac.compare_digest(supplied, expected)


class BearerAuthMiddleware:
    """ASGI middleware (not BaseHTTPMiddleware: must not buffer SSE streams).

    Guards every path except GET /health. 401 body never echoes the token.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not (
            scope["method"] == "GET" and scope["path"] == "/health"
        ):
            if not _allowed(Request(scope, receive)):
                resp = JSONResponse(
                    {"error": {"code": "unauthorized",
                               "message": "missing or invalid bearer token"}},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


async def _health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "transport": "streamable-http"})


def _transport_security():
    """DNS-rebinding protection for non-loopback binds.

    The SDK auto-enables it only for loopback hosts; behind a reverse proxy we
    validate the Host header against FAIRVALUE_MCP_ALLOWED_HOSTS (comma list).
    """
    hosts = [h.strip() for h in
             os.environ.get("FAIRVALUE_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if not hosts:
        return None  # loopback: SDK default protection applies
    from mcp.server.transport_security import TransportSecuritySettings
    origins: list[str] = []
    for h in hosts:
        origins += [f"https://{h}", f"http://{h}"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def create_app():
    """Starlette app: streamable-http MCP endpoint + /health + bearer auth."""
    app = mcp.streamable_http_app(transport_security=_transport_security())
    app.add_middleware(BearerAuthMiddleware)
    app.router.routes.insert(0, Route("/health", _health, methods=["GET"]))
    return app


def main() -> None:  # console entrypoint
    import uvicorn

    host = os.environ.get("FAIRVALUE_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("FAIRVALUE_MCP_PORT", "8001"))
    if not _expected_token() and not _anon_allowed():
        raise SystemExit(
            "refusing to start: set FAIRVALUE_MCP_TOKEN (or FAIRVALUE_API_KEY), "
            "or FAIRVALUE_MCP_ALLOW_ANON=1 for loopback development only")
    if host not in _LOOPBACK and not _expected_token():
        raise SystemExit(
            "refusing to bind a non-loopback host without a token "
            "(set FAIRVALUE_MCP_TOKEN)")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

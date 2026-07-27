"""Network transport for the MCP server: a token gate over FastMCP's HTTP app.

Claude Code talks to the server over stdio, but a *shared* server (e.g. added to
claude.ai as a custom connector, behind nginx/TLS) needs a network transport plus
an authentication boundary. This module supplies both:

* :func:`extract_token` — read the token from ``?token=…`` or an
  ``Authorization: Bearer …`` header (an ASGI scope).
* :class:`TokenAuthMiddleware` — a tiny ASGI middleware that rejects requests
  without the right token (401), except for explicitly *open* path prefixes.
* :func:`build_http_app` / :func:`run_http` — wrap FastMCP's ``sse_app`` /
  ``streamable_http_app`` with the gate and run it under uvicorn.

Why the message path is left open (SSE): after an authenticated ``GET /sse`` the
server hands the client a POST url ``/messages/?session_id=<hex>`` *without* the
token (see ``mcp.server.sse``). Gating that path would break the session on the
first message. It stays reachable but is protected transitively — a session only
exists after a valid token opened the stream, and the 128-bit ``session_id`` is
unguessable, so an unauthenticated POST resolves to "session not found".
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


def extract_token(scope) -> str | None:
    """Pull the auth token from an ASGI ``scope``: ``?token=…`` then Bearer."""
    qs = scope.get("query_string") or b""
    if qs:
        values = parse_qs(qs.decode("latin-1")).get("token")
        if values:
            return values[0]
    for name, value in scope.get("headers") or []:
        if name == b"authorization":
            raw = value.decode("latin-1")
            if raw.lower().startswith("bearer "):
                return raw[7:].strip()
    return None


def _token_ok(provided: str | None, expected: str) -> bool:
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided, expected)


class TokenAuthMiddleware:
    """Reject requests that don't carry ``token`` (401), except ``open_paths``.

    ``open_paths`` are prefixes that bypass the token check but still reach the
    wrapped app — used for the SSE message endpoint, which is self-protected by
    an unguessable ``session_id`` issued only after authenticated ``/sse``.
    """

    def __init__(self, app, token: str, open_paths=()) -> None:
        if not token:
            raise ValueError("TokenAuthMiddleware requires a non-empty token")
        self.app = app
        self.token = token
        self.open_paths = tuple(open_paths)

    async def __call__(self, scope, receive, send) -> None:
        typ = scope.get("type")
        if typ not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if self._is_open(path) or _token_ok(extract_token(scope), self.token):
            await self.app(scope, receive, send)
            return
        await self._reject(typ, send)

    def _is_open(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.open_paths)

    async def _reject(self, typ: str, send) -> None:
        if typ == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send(
            {"type": "http.response.body", "body": b'{"error":"unauthorized"}'}
        )


def _apply_transport_security(mcp, config) -> None:
    """Configure DNS-rebinding protection for a public deployment.

    Behind nginx the ``Host`` is the public domain, which FastMCP's default
    localhost-only allow-list would reject. With ``allowed_hosts`` set we honour
    it; otherwise we disable the check (the token gate + TLS are the boundary).
    """
    from mcp.server.transport_security import TransportSecuritySettings

    if config.allowed_hosts:
        hosts = list(config.allowed_hosts)
        origins = [f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts]
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origins,
        )
    else:
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )


def build_http_app(mcp, config):
    """Return the ASGI app for the configured network transport, token-gated."""
    mcp.settings.host = config.host
    mcp.settings.port = config.port
    _apply_transport_security(mcp, config)

    if config.transport == "streamable-http":
        app = mcp.streamable_http_app()
        open_paths: tuple[str, ...] = ()
    else:  # "sse"
        app = mcp.sse_app()
        # POST url handed to the client after auth; session_id-protected.
        open_paths = (mcp.settings.message_path,)

    if config.auth_token:
        app = TokenAuthMiddleware(app, config.auth_token, open_paths=open_paths)
    else:
        logger.warning(
            "MCP %s transport is running WITHOUT a token gate "
            "(set MCP_AUTH_TOKEN to require one).",
            config.transport,
        )
    return app


def run_http(mcp, config) -> None:  # pragma: no cover - needs a live server
    """Run the token-gated network app under uvicorn."""
    import uvicorn

    app = build_http_app(mcp, config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")

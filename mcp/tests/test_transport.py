"""The network transport: token extraction + the token gate over FastMCP."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from sdlc_mcp.config import Config
from sdlc_mcp.transport import (
    TokenAuthMiddleware,
    build_http_app,
    extract_token,
)


# --------------------------------------------------------------------------- #
# extract_token
# --------------------------------------------------------------------------- #
def _scope(query: bytes = b"", headers=None) -> dict:
    return {"type": "http", "query_string": query, "headers": headers or []}


def test_extract_token_from_query():
    assert extract_token(_scope(query=b"token=abc")) == "abc"


def test_extract_token_from_bearer_header():
    scope = _scope(headers=[(b"authorization", b"Bearer abc")])
    assert extract_token(scope) == "abc"


def test_extract_token_absent():
    assert extract_token(_scope()) is None


# --------------------------------------------------------------------------- #
# TokenAuthMiddleware — a trivial inner app so we test the gate, not SSE
# --------------------------------------------------------------------------- #
async def _echo_app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


def _client(token="secret", open_paths=()):
    app = TokenAuthMiddleware(_echo_app, token, open_paths=open_paths)
    return TestClient(app)


def test_gate_requires_nonempty_token():
    with pytest.raises(ValueError):
        TokenAuthMiddleware(_echo_app, "")


def test_gate_rejects_missing_token():
    with _client() as c:
        assert c.get("/sse").status_code == 401


def test_gate_rejects_wrong_token():
    with _client() as c:
        assert c.get("/sse?token=nope").status_code == 401


def test_gate_401_has_no_oauth_challenge():
    # A `WWW-Authenticate: Bearer` challenge makes claude.ai's connector try
    # OAuth Dynamic Client Registration instead of connecting with the ?token=
    # URL, which fails. The 401 must NOT advertise an auth challenge.
    with _client() as c:
        r = c.get("/sse")
        assert r.status_code == 401
        assert "www-authenticate" not in {k.lower() for k in r.headers}


def test_gate_allows_query_token():
    with _client() as c:
        r = c.get("/sse?token=secret")
        assert r.status_code == 200 and r.text == "ok"


def test_gate_allows_bearer_token():
    with _client() as c:
        r = c.get("/sse", headers={"Authorization": "Bearer secret"})
        assert r.status_code == 200


def test_gate_lets_open_path_through_without_token():
    # The SSE message endpoint is reachable without the token (session-protected).
    with _client(open_paths=("/messages/",)) as c:
        r = c.get("/messages/?session_id=abc")
        assert r.status_code == 200 and r.text == "ok"
    # …but any other path still needs it.
    with _client(open_paths=("/messages/",)) as c:
        assert c.get("/sse").status_code == 401


# --------------------------------------------------------------------------- #
# build_http_app — the real FastMCP app, gated
# --------------------------------------------------------------------------- #
def _http_cfg(tmp_path: Path, **over) -> Config:
    base = dict(
        sdlc_root=tmp_path,
        audit_db=tmp_path / "a.db",
        transcript_dir=tmp_path / "tr",
        actor_human="x",
        actor_agent="t",
        app_repo=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        gh_token=None,
        transport="sse",
        host="127.0.0.1",
        port=9123,
        auth_token="secret",
        allowed_hosts=(),
    )
    base.update(over)
    return Config(**base)


def test_build_http_app_gates_sse(tmp_path):
    from sdlc_mcp import server

    app = build_http_app(server.mcp, _http_cfg(tmp_path))
    with TestClient(app) as c:
        # Rejected before the SSE stream opens -> no hang.
        assert c.get("/sse").status_code == 401


def test_build_http_app_leaves_message_path_open(tmp_path):
    from sdlc_mcp import server

    app = build_http_app(server.mcp, _http_cfg(tmp_path))
    with TestClient(app) as c:
        # Reaches the real handler (unknown session -> not a 401 from the gate).
        r = c.get("/messages/?session_id=00000000000000000000000000000000")
        assert r.status_code != 401


def test_build_http_app_applies_host_port(tmp_path):
    from sdlc_mcp import server

    build_http_app(server.mcp, _http_cfg(tmp_path, host="0.0.0.0", port=9999))
    assert server.mcp.settings.host == "0.0.0.0"
    assert server.mcp.settings.port == 9999

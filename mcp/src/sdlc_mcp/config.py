"""Runtime configuration, resolved from the environment with sane defaults.

Only the MCP/service layer uses this — the ``law/`` functions always take an
explicit ``sdlc_root`` so they never depend on ambient config. Secrets
(Telegram, GitHub) are read here but stay ``None`` until the operator provides
them (see ``docs/SETUP.md``); the integrations degrade to fakes without them.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    # this file: <repo>/mcp/src/sdlc_mcp/config.py
    return Path(__file__).resolve().parents[3]


def _mcp_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_user() -> str | None:
    try:
        out = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


@dataclass(frozen=True)
class Config:
    sdlc_root: Path
    audit_db: Path
    transcript_dir: Path
    actor_human: str
    actor_agent: str
    app_repo: Path | None
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    gh_token: str | None
    # Transport: "stdio" (Claude Code, default) or a network transport
    # ("sse" / "streamable-http") for a shared server behind nginx.
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    # Token required on the connection URL (?token=…) / as a Bearer header when
    # served over the network. None => the gate is not installed (local only).
    auth_token: str | None = None
    # Hosts allowed by DNS-rebinding protection. Empty => protection disabled
    # (the token gate + TLS/nginx are the boundary for a public connector).
    allowed_hosts: tuple[str, ...] = ()
    # Default base branch for PRs into the app repo (project-specific).
    app_base_branch: str = "develop"
    # Command the coding toolbelt runs for app_test (project-specific).
    app_test_cmd: str = "flutter test"


def _maybe_load_dotenv() -> None:
    """Best-effort: load ``mcp/.env`` so secrets can live there, not in configs."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(_mcp_root() / ".env")


def load_config(env: dict | None = None) -> Config:
    if env is None:
        _maybe_load_dotenv()
        env = os.environ
    repo, mcp = _repo_root(), _mcp_root()
    var = mcp / "var"

    # The engine is project-agnostic: real use sets SDLC_ROOT to the target
    # project's sdlc/ tree (e.g. .../agro_system/sdlc). The bundled example is
    # only a fallback for local smoke/demo.
    sdlc_root = Path(
        env.get("SDLC_ROOT") or (repo / "examples" / "mini-sdlc")
    ).expanduser().resolve()
    audit_db = Path(env.get("AUDIT_DB") or (var / "audit.db")).expanduser()
    transcript_dir = Path(
        env.get("TRANSCRIPT_DIR") or (var / "transcripts")
    ).expanduser()
    app_repo = env.get("APP_REPO_PATH")

    transport = (env.get("MCP_TRANSPORT") or "stdio").strip().lower()
    host = env.get("MCP_HOST") or "127.0.0.1"
    port = int(env.get("MCP_PORT") or 8000)
    auth_token = env.get("MCP_AUTH_TOKEN") or None
    allowed_hosts = tuple(
        h.strip()
        for h in (env.get("MCP_ALLOWED_HOSTS") or "").split(",")
        if h.strip()
    )

    return Config(
        sdlc_root=sdlc_root,
        audit_db=audit_db,
        transcript_dir=transcript_dir,
        actor_human=env.get("ACTOR_HUMAN") or _git_user() or "unknown",
        actor_agent=env.get("ACTOR_AGENT") or "claude-code",
        app_repo=Path(app_repo).expanduser().resolve() if app_repo else None,
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=env.get("TELEGRAM_CHAT_ID"),
        gh_token=env.get("GH_TOKEN"),
        transport=transport,
        host=host,
        port=port,
        auth_token=auth_token,
        allowed_hosts=allowed_hosts,
        app_base_branch=env.get("APP_BASE_BRANCH") or "develop",
        app_test_cmd=env.get("APP_TEST_CMD") or "flutter test",
    )

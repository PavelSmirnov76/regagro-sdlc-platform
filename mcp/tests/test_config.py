from sdlc_mcp.config import load_config


def test_load_config_from_env(tmp_path):
    env = {
        "SDLC_ROOT": str(tmp_path / "sdlc"),
        "AUDIT_DB": str(tmp_path / "a.db"),
        "TRANSCRIPT_DIR": str(tmp_path / "tr"),
        "ACTOR_HUMAN": "pavel",
        "APP_REPO_PATH": str(tmp_path / "app"),
    }
    cfg = load_config(env)
    assert cfg.actor_human == "pavel"
    assert cfg.actor_agent == "claude-code"
    assert cfg.sdlc_root == (tmp_path / "sdlc").resolve()
    assert cfg.app_repo == (tmp_path / "app").resolve()
    assert cfg.telegram_bot_token is None  # absent -> None (integrations fall back)


def test_defaults_point_into_repo(tmp_path):
    cfg = load_config({"ACTOR_HUMAN": "x"})
    # No project tree of its own: the default falls back to the bundled example.
    assert cfg.sdlc_root.name == "mini-sdlc"
    assert cfg.sdlc_root.parent.name == "examples"
    assert cfg.audit_db.name == "audit.db"
    assert cfg.transcript_dir.name == "transcripts"


def test_transport_defaults_to_stdio():
    cfg = load_config({"ACTOR_HUMAN": "x"})
    assert cfg.transport == "stdio"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8000
    assert cfg.auth_token is None
    assert cfg.allowed_hosts == ()


def test_app_base_branch_config():
    assert load_config({"ACTOR_HUMAN": "x"}).app_base_branch == "develop"
    assert (
        load_config({"APP_BASE_BRANCH": "develop_shz_rewirte"}).app_base_branch
        == "develop_shz_rewirte"
    )


def test_transport_from_env():
    cfg = load_config(
        {
            "MCP_TRANSPORT": "SSE",  # normalised to lower-case
            "MCP_HOST": "0.0.0.0",
            "MCP_PORT": "9001",
            "MCP_AUTH_TOKEN": "s3cret",
            "MCP_ALLOWED_HOSTS": "ra-mcp-4.skobeltsyn.com, localhost:*",
        }
    )
    assert cfg.transport == "sse"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9001
    assert cfg.auth_token == "s3cret"
    assert cfg.allowed_hosts == ("ra-mcp-4.skobeltsyn.com", "localhost:*")

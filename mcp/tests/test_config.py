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
    assert cfg.sdlc_root.name == "sdlc"
    assert cfg.audit_db.name == "audit.db"
    assert cfg.transcript_dir.name == "transcripts"

"""The coding toolbelt over the app repo — path confinement is the key check."""

import subprocess

import pytest

from sdlc_mcp.law import app_repo


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "app"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=r, check=True)
    (r / "lib").mkdir()
    (r / "lib" / "main.dart").write_text("void main() {}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=r, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=r,
        check=True,
    )
    return r


def test_read_file(repo):
    assert "void main" in app_repo.read_file(repo, "lib/main.dart")


def test_write_file_roundtrip(repo):
    res = app_repo.write_file(repo, "lib/new.dart", "// new\n")
    assert res["existed"] is False and res["path"] == "lib/new.dart"
    assert app_repo.read_file(repo, "lib/new.dart") == "// new\n"
    res2 = app_repo.write_file(repo, "lib/new.dart", "// changed\n")
    assert res2["existed"] is True


def test_path_confinement_blocks_escape(repo):
    for bad in ["../secret", "../../etc/passwd", "/etc/passwd"]:
        with pytest.raises(app_repo.AppRepoError):
            app_repo.read_file(repo, bad)
    with pytest.raises(app_repo.AppRepoError):
        app_repo.write_file(repo, "../evil.txt", "x")
    assert not (repo.parent / "evil.txt").exists()


def test_list_dir_hides_git(repo):
    assert {e["name"] for e in app_repo.list_dir(repo, "lib")} == {"main.dart"}
    assert ".git" not in {e["name"] for e in app_repo.list_dir(repo)}


def test_search(repo):
    hits = app_repo.search(repo, "void main")
    assert any(h["file"] == "lib/main.dart" and h["line"] == 1 for h in hits)
    assert app_repo.search(repo, "nonexistent-zzz") == []


def test_branch_commit_diff(repo):
    app_repo.create_branch(repo, "feat/x")
    assert app_repo.current_branch(repo) == "feat/x"
    app_repo.write_file(repo, "lib/main.dart", "void main() { print('hi'); }\n")
    assert "print" in app_repo.diff(repo)
    c = app_repo.commit_all(repo, "feat: hi")
    assert c["sha"] and c["branch"] == "feat/x"
    assert app_repo.diff(repo).strip() == ""  # nothing left uncommitted


def test_run_check(repo):
    assert app_repo.run_check(repo, "true")["ok"] is True
    bad = app_repo.run_check(repo, "false")
    assert bad["ok"] is False and bad["code"] == 1


def test_service_app_write_and_commit_audited(repo, mini_sdlc, tmp_path):
    from sdlc_mcp.config import Config
    from sdlc_mcp.service import SdlcService

    cfg = Config(
        sdlc_root=mini_sdlc,
        audit_db=tmp_path / "a.db",
        transcript_dir=tmp_path / "tr",
        actor_human="p",
        actor_agent="t",
        app_repo=repo,
        telegram_bot_token=None,
        telegram_chat_id=None,
        gh_token=None,
    )
    svc = SdlcService(cfg)
    svc.app_create_branch(name="feat/toolbelt")
    svc.app_write_file(path="lib/added.dart", content="// added\n")
    svc.app_commit(message="feat: add")
    actions = {h["action"] for h in svc.audit_history()}
    assert {"app_create_branch", "app_write_file", "app_commit"} <= actions
    kinds = {e["kind"] for e in svc.transcript_read()}
    assert {"app_write_file", "app_commit"} <= kinds

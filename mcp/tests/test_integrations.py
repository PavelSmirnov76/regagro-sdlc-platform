from pathlib import Path

from sdlc_mcp.config import Config
from sdlc_mcp.integrations import factory, fakes


def _cfg(tmp_path: Path, **over) -> Config:
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
    )
    base.update(over)
    return Config(**base)


def test_factory_defaults_to_fakes(tmp_path):
    ig = factory.build(_cfg(tmp_path))
    assert isinstance(ig.git, fakes.FakeGitOps)
    assert isinstance(ig.apk, fakes.FakeApkBuilder)
    assert isinstance(ig.telegram, fakes.FakeTelegramSender)
    assert isinstance(ig.release, fakes.FakeReleaseUploader)


def test_factory_uses_real_telegram_when_credentials_present(tmp_path):
    from sdlc_mcp.integrations.telegram import RealTelegramSender

    ig = factory.build(_cfg(tmp_path, telegram_bot_token="123:ABC", telegram_chat_id="42"))
    assert isinstance(ig.telegram, RealTelegramSender)


def test_fake_git_records_call():
    g = fakes.FakeGitOps()
    res = g.open_pull_request(repo=None, base="develop", head="feat/x", title="T", body="B")
    assert res.used_fake and res.ok and res.branch == "feat/x"
    assert g.calls and g.calls[0][0] == "open_pull_request"


def test_fake_apk_and_telegram():
    a = fakes.FakeApkBuilder()
    r = a.build(repo=None, flavor="prod")
    assert r.used_fake and r.apk_path and r.flavor == "prod"

    t = fakes.FakeTelegramSender()
    d = t.send_document(path="x.apk", caption="c")
    assert d.used_fake and d.ok


def test_service_open_pull_request_fake_is_audited(service):
    res = service.open_pull_request(title="Add QR scan", body="...", head="feat/qr")
    assert res["used_fake"] is True and res["ok"] is True
    assert any(r["action"] == "open_pull_request" for r in service.audit_history())


def test_service_build_and_deliver_apk_fake_is_audited(service):
    res = service.build_and_deliver_apk(flavor="prod")
    assert res["build"]["used_fake"] is True
    assert res["release"]["used_fake"] is True
    assert any(r["action"] == "build_and_deliver_apk" for r in service.audit_history())


def test_fake_apk_records_mode():
    b = fakes.FakeApkBuilder()
    res = b.build(repo=None, flavor="dev", mode="debug")
    assert res.used_fake and res.apk_path.endswith("app-dev-debug.apk")
    assert b.calls[-1][1]["mode"] == "debug"

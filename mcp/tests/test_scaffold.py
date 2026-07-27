"""Scaffold: port of sdlc-scaffold.sh — drop the pipeline into a target repo."""

from pathlib import Path

from sdlc_mcp.law import scaffold


def _scaffold(target, **kw):
    return scaffold.scaffold_tree(target, **kw)


def test_creates_pipeline_tree(tmp_path):
    r = _scaffold(tmp_path / "proj")
    root = tmp_path / "proj" / "sdlc"
    assert (root / "RUNBOOK.md").is_file()
    assert (root / "AGENTS.md").is_file()
    assert (root / "0-vibes" / "AGENTS.md").is_file()
    assert (root / "2-specs" / "actors" / "CLAUDE.md").is_file()
    assert r.created and not r.skipped
    assert r.container == "sdlc"


def test_substitutes_project_name(tmp_path):
    _scaffold(tmp_path / "proj", project_name="Lifestocks")
    root = tmp_path / "proj" / "sdlc"
    assert "Lifestocks" in (root / "AGENTS.md").read_text(encoding="utf-8")
    leftovers = [
        p
        for p in root.rglob("*")
        if p.is_file() and "{{PROJECT_NAME}}" in p.read_text(encoding="utf-8")
    ]
    assert leftovers == []


def test_idempotent_second_run_skips(tmp_path):
    _scaffold(tmp_path / "proj")
    r2 = _scaffold(tmp_path / "proj")
    assert r2.created == []
    assert r2.skipped
    assert r2.backup is None


def test_force_backs_up_before_overwrite(tmp_path):
    _scaffold(tmp_path / "proj")
    marker = tmp_path / "proj" / "sdlc" / "AGENTS.md"
    marker.write_text("HAND EDITED", encoding="utf-8")
    r = _scaffold(tmp_path / "proj", force=True)
    assert r.backup is not None
    assert (Path(r.backup) / "AGENTS.md").read_text(encoding="utf-8") == "HAND EDITED"
    assert "HAND EDITED" not in marker.read_text(encoding="utf-8")


def test_host_pointer_added_once(tmp_path):
    target = tmp_path / "proj"
    _scaffold(target)
    cm = target / "CLAUDE.md"
    body = cm.read_text(encoding="utf-8")
    opening = f"<!-- {scaffold.POINTER_MARK} -->"
    assert opening in body and "RUNBOOK.md" in body
    assert body.count(opening) == 1
    _scaffold(target)  # idempotent: no duplicate pointer
    assert cm.read_text(encoding="utf-8").count(opening) == 1


def test_host_pointer_prefers_dot_claude(tmp_path):
    target = tmp_path / "proj"
    (target / ".claude").mkdir(parents=True)
    (target / ".claude" / "CLAUDE.md").write_text("# existing\n", encoding="utf-8")
    r = _scaffold(target)
    assert r.host_pointer.endswith("/.claude/CLAUDE.md")
    assert not (target / "CLAUDE.md").exists()


def test_flat_mode_writes_at_root_no_pointer(tmp_path):
    target = tmp_path / "proj"
    r = _scaffold(target, container=".")
    assert (target / "RUNBOOK.md").is_file()
    assert r.container == "."
    assert r.host_pointer is None
    # flat mode ships the pipeline's own root CLAUDE.md stub, but no host pointer
    assert scaffold.POINTER_MARK not in (target / "CLAUDE.md").read_text(
        encoding="utf-8"
    )


def test_dry_run_writes_nothing(tmp_path):
    target = tmp_path / "proj"
    r = _scaffold(target, dry_run=True)
    assert r.dry_run and r.created
    assert not (target / "sdlc").exists()
    assert not (target / "CLAUDE.md").exists()


def test_service_scaffold_records_audit_and_transcript(service, tmp_path):
    res = service.scaffold_project(
        target=str(tmp_path / "newproj"), project_name="Demo"
    )
    assert res["created"] and res["container"] == "sdlc"
    assert any(h["action"] == "scaffold_project" for h in service.audit_history())
    assert any(e.get("kind") == "scaffold_project" for e in service.transcript_read())

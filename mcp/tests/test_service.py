from sdlc_mcp.law import artifacts, ids, prd


def test_business_task_create_writes_audits_transcribes(service):
    res = service.create_business_task(
        name="BOARD",
        title="Специфицировать модуль BOARD",
        requirements=["R12"],
        acceptance=["MOD написан"],
    )
    assert res["id"] == "BT-2"
    assert res["path"] == "1-business-tasks/planning/BT-2-PLANNING-BOARD.md"

    content = artifacts.read(service.root, "BT-2")
    assert "# BT-2 — Специфицировать модуль BOARD" in content
    assert "[R12](../../0-vibes/prd/PRD.md)" in content

    hist = service.audit_history(artifact_id="BT-2")
    assert hist and hist[0]["action"] == "create_business_task"
    assert hist[0]["actor_human"] == "pavel"
    assert hist[0]["new_hash"]

    kinds = [e["kind"] for e in service.transcript_read()]
    assert "artifact_created" in kinds


def test_module_create_cites_bt(service):
    res = service.create_module(name="BOARD", derived_from_bt="BT-1", purpose="объявления")
    assert res["id"] == "MOD-3"  # MOD-1 live + MOD-2 obsolete -> MOD-3
    content = artifacts.read(service.root, "MOD-3")
    assert "[BT-1](../../1-business-tasks/planning/BT-1-PLANNING-AUTH.md)" in content


def test_supersede_through_create(service):
    res = service.create_module(name="AUTH2", derived_from_bt="BT-1", supersede_of="MOD-1")
    assert res["superseded"] == "MOD-1"
    assert ids.resolve(service.root, "MOD-1").is_obsolete is True
    assert ids.resolve(service.root, res["id"]).is_obsolete is False
    assert "supersedes MOD-1" in artifacts.read(service.root, res["id"])
    actions = {r["action"] for r in service.audit_history()}
    assert {"create_module", "entomb"} <= actions


def test_use_case_create_links_and_filename(service):
    res = service.create_use_case(
        actor_id="ACTOR-1",
        evt_id="EVT-1",
        ent_id="ENT-1",
        crud="read",
        outcome="ok",
        module="AUTH",
        title="Читает профиль",
    )
    assert res["path"].endswith("UC-2-ACTOR-1-EVT-1-ENT-1-READ_OK-IN-AUTH.md")
    content = artifacts.read(service.root, res["id"])
    assert "[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)" in content
    assert "[EVT-1](../events/EVT-1-USER-SELF-REGISTERED-IN-AUTH.md)" in content


def test_prd_add_requirement_snapshots_and_audits(service):
    res = service.prd_add_requirement("Новое требование про X.")
    assert res["id"] == "R15"
    assert "**R15**" in prd.read(service.root)
    snapshots = list((service.root / "0-vibes/prd/history").glob("PRD-*.md"))
    assert snapshots
    assert any(r["action"] == "prd_add_requirement" for r in service.audit_history())


def test_entomb_artifact_records(service):
    service.entomb_artifact("ACTOR-1", why="не используется")
    assert ids.resolve(service.root, "ACTOR-1").is_obsolete is True
    assert any(
        r["action"] == "entomb" for r in service.audit_history(artifact_id="ACTOR-1")
    )


def test_validate_via_service(service):
    assert service.validate()["ok"] is True


def test_every_mutation_is_audited(service):
    """No create/entomb/prd op leaves the ledger empty — the core guarantee."""
    before = len(service.audit_history(limit=1000))
    service.create_business_task(name="MOVE", requirements=["R12"])
    service.entomb_artifact("EVT-1", why="test")
    service.prd_add_requirement("Ещё одно.")
    after = len(service.audit_history(limit=1000))
    assert after - before == 3

import pytest

from sdlc_mcp.law import templates as t


def test_slug():
    assert t.slug("QR visual tag scan") == "QR-VISUAL-TAG-SCAN"
    assert t.slug("rfid_settings") == "RFID-SETTINGS"


def test_business_task_planning():
    rel, content = t.business_task_planning(
        bt_id="BT-2",
        name="BOARD",
        title="Специфицировать модуль BOARD",
        requirement_links=["[R12](../../0-vibes/prd/PRD.md)"],
        acceptance=["MOD написан"],
    )
    assert rel == "1-business-tasks/planning/BT-2-PLANNING-BOARD.md"
    assert "# BT-2 — Специфицировать модуль BOARD" in content
    assert "- [ ] MOD написан" in content
    assert "[R12](../../0-vibes/prd/PRD.md)" in content
    for section in ("## Текущее состояние", "## Что делать", "## Критерии приёмки"):
        assert section in content


def test_business_task_observation_severity_dir():
    rel, _ = t.business_task_observation(
        bt_id="BT-3", severity="error", name="CRASH", requirement_links=[]
    )
    assert rel == "1-business-tasks/observation/errors/BT-3-ERROR-CRASH.md"
    with pytest.raises(ValueError):
        t.business_task_observation(bt_id="BT-3", severity="NOPE", name="X", requirement_links=[])


def test_module_filename():
    rel, content = t.module(mod_id="MOD-3", name="board", derived_from_link="[BT-2](x.md)")
    assert rel == "2-specs/modules/MOD-3-BOARD.md"
    assert "# MOD-3 — BOARD" in content
    for s in ("## Назначение", "## Состав", "## Граница"):
        assert s in content


def test_actor_filename():
    rel, _ = t.actor(actor_id="ACTOR-2", name="scanner", module="inv", title="Сканер")
    assert rel == "2-specs/actors/ACTOR-2-SCANNER-IN-INV.md"


def test_use_case_filename_and_result():
    rel, content = t.use_case(
        uc_id="UC-2",
        actor_id="ACTOR-1",
        evt_id="EVT-1",
        ent_id="ENT-1",
        crud="create",
        outcome="ok",
        module="auth",
        title="Тест",
        actor_link="[ACTOR-1](../actors/A.md)",
        event_link="[EVT-1](../events/E.md)",
        entity_links=["[ENT-1](../entities/N.md)"],
    )
    assert rel == "2-specs/use-cases/UC-2-ACTOR-1-EVT-1-ENT-1-CREATE_OK-IN-AUTH.md"
    assert "## Открытые вопросы и ограничения" in content


def test_use_case_rejects_bad_vocabulary():
    with pytest.raises(ValueError):
        t.use_case(
            uc_id="UC-2", actor_id="ACTOR-1", evt_id="EVT-1", ent_id="ENT-1",
            crud="FROB", outcome="OK", module="AUTH", title="x",
            actor_link="a", event_link="e", entity_links=["n"],
        )

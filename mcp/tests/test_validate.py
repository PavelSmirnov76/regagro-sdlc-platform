from sdlc_mcp.law import entomb, validate


def test_validate_clean_tree(mini_sdlc):
    rep = validate.validate_tree(mini_sdlc)
    assert rep.ok
    assert rep.collisions == []
    assert rep.unresolved == []
    assert rep.stale == []
    assert rep.broken_links == []


def test_validate_detects_id_collision(mini_sdlc):
    (mini_sdlc / "2-specs/modules/MOD-1-DUPLICATE.md").write_text("# MOD-1 dup\n")
    rep = validate.validate_tree(mini_sdlc)
    assert "MOD-1" in rep.collisions
    assert not rep.ok


def test_validate_flags_stale_citation_but_stays_ok(mini_sdlc):
    # ENT-1 is cited by EVT-1 and UC-1; entombing it makes those citations stale.
    entomb.entomb(mini_sdlc, "ENT-1", when="2026-07-26", why="test", superseded_by="ENT-9")
    rep = validate.validate_tree(mini_sdlc)
    stale_ids = {cid for _f, cid in rep.stale}
    assert "ENT-1" in stale_ids
    assert rep.ok  # stale is advisory, not a hard failure
    assert rep.as_dict()["ok"] is True


def test_validate_ignores_non_managed_id_prefixes(mini_sdlc):
    # Tracker-named tasks mirror task<->result by identical filename; the shared
    # leading "SHEEP-9" must not read as a collision.
    (mini_sdlc / "4-tasks").mkdir(parents=True, exist_ok=True)
    (mini_sdlc / "4-tasks/SHEEP-9-1-A.md").write_text("# task\n")
    (mini_sdlc / "5-results").mkdir(parents=True, exist_ok=True)
    (mini_sdlc / "5-results/SHEEP-9-1-A.md").write_text("# result\n")
    rep = validate.validate_tree(mini_sdlc)
    assert "SHEEP-9" not in rep.collisions
    assert rep.ok


def test_validate_flags_unresolved_citation(mini_sdlc):
    p = mini_sdlc / "2-specs/modules/MOD-1-AUTH.md"
    p.write_text(p.read_text() + "\n\nсм. [BT-404](../../nope.md)\n")
    rep = validate.validate_tree(mini_sdlc)
    unresolved_ids = {cid for _f, cid in rep.unresolved}
    assert "BT-404" in unresolved_ids

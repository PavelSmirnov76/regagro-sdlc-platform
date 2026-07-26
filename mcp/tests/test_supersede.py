import pytest

from sdlc_mcp.law import artifacts, ids, supersede


def test_supersede_writes_new_then_entombs_old(mini_sdlc):
    res = supersede.supersede(
        mini_sdlc,
        old_id="MOD-1",
        new_id="MOD-3",
        new_rel_path="2-specs/modules/MOD-3-AUTH2.md",
        new_content="- **supersedes**: MOD-1\n\n# MOD-3 — AUTH2\n",
        when="2026-07-26",
        why="reworked",
    )
    assert res.new_path.exists()
    assert ids.resolve(mini_sdlc, "MOD-3").is_obsolete is False
    assert ids.resolve(mini_sdlc, "MOD-1").is_obsolete is True
    assert "supersedes" in artifacts.read(mini_sdlc, "MOD-3")


def test_supersede_aborts_on_name_collision(mini_sdlc):
    # New path collides with a frozen file -> nothing is entombed.
    with pytest.raises(artifacts.FrozenViolation):
        supersede.supersede(
            mini_sdlc,
            old_id="MOD-1",
            new_id="MOD-3",
            new_rel_path="2-specs/modules/MOD-1-AUTH.md",  # already exists
            new_content="x",
            when="2026-07-26",
            why="oops",
        )
    assert ids.resolve(mini_sdlc, "MOD-1").is_obsolete is False  # old still live

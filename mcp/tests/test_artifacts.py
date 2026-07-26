import pytest

from sdlc_mcp.law import artifacts


def test_read(mini_sdlc):
    assert "MOD-1 — AUTH" in artifacts.read(mini_sdlc, "MOD-1")


def test_read_missing(mini_sdlc):
    with pytest.raises(FileNotFoundError):
        artifacts.read(mini_sdlc, "MOD-999")


def test_write_new_creates(mini_sdlc):
    p = artifacts.write_new(mini_sdlc, "2-specs/modules/MOD-3-BOARD.md", "# MOD-3 — BOARD\n")
    assert p.exists()
    assert artifacts.read(mini_sdlc, "MOD-3") == "# MOD-3 — BOARD\n"


def test_write_new_refuses_overwrite(mini_sdlc):
    with pytest.raises(artifacts.FrozenViolation):
        artifacts.write_new(mini_sdlc, "2-specs/modules/MOD-1-AUTH.md", "clobber")


def test_list_type(mini_sdlc):
    refs = artifacts.list_type(mini_sdlc, "MOD")
    by_id = {r.id: r for r in refs}
    assert by_id["MOD-1"].is_obsolete is False
    assert by_id["MOD-2"].is_obsolete is True

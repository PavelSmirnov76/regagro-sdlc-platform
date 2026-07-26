import pytest

from sdlc_mcp.law import entomb, ids


def test_entomb_moves_and_headers(mini_sdlc):
    dest = entomb.entomb(
        mini_sdlc, "MOD-1", when="2026-07-26", why="merged into BOARD", superseded_by="MOD-9"
    )
    assert dest.exists()
    assert "obsolete" in dest.parts
    body = dest.read_text(encoding="utf-8")
    assert "**Entombed:** 2026-07-26" in body
    assert "**Superseded by:** MOD-9" in body
    assert "# MOD-1 — AUTH" in body  # original content preserved

    ref = ids.resolve(mini_sdlc, "MOD-1")
    assert ref is not None and ref.is_obsolete  # no live MOD-1 remains


def test_entomb_unknown_id(mini_sdlc):
    with pytest.raises(entomb.EntombError):
        entomb.entomb(mini_sdlc, "MOD-777", when="x", why="y")


def test_entomb_already_entombed(mini_sdlc):
    with pytest.raises(entomb.EntombError):
        entomb.entomb(mini_sdlc, "MOD-2", when="x", why="y")  # already in obsolete/

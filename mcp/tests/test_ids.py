import pytest

from sdlc_mcp.law import ids


def test_id_type_and_number():
    assert ids.id_type("BT-13") == "BT"
    assert ids.id_number("BT-13") == 13
    with pytest.raises(ValueError):
        ids.id_type("nonsense")
    with pytest.raises(ValueError):
        ids.id_number("R7")  # R is not a FULL_ID here (no bare-number form)


def test_allocate_next_per_type(mini_sdlc):
    assert ids.allocate(mini_sdlc, "BT") == "BT-2"
    assert ids.allocate(mini_sdlc, "ACTOR") == "ACTOR-2"
    assert ids.allocate(mini_sdlc, "UC") == "UC-2"


def test_allocate_counts_obsolete(mini_sdlc):
    # MOD-1 live + MOD-2 entombed -> next is MOD-3, never reusing 2.
    assert ids.allocate(mini_sdlc, "MOD") == "MOD-3"


def test_allocate_fresh_type_starts_at_one(mini_sdlc):
    assert ids.allocate(mini_sdlc, "FIG") == "FIG-1"


def test_allocate_rejects_unknown_type(mini_sdlc):
    with pytest.raises(ValueError):
        ids.allocate(mini_sdlc, "NOPE")


def test_resolve_live(mini_sdlc):
    ref = ids.resolve(mini_sdlc, "MOD-1")
    assert ref is not None and not ref.is_obsolete
    assert ref.path.name == "MOD-1-AUTH.md"


def test_resolve_obsolete_only(mini_sdlc):
    ref = ids.resolve(mini_sdlc, "MOD-2")
    assert ref is not None and ref.is_obsolete


def test_resolve_missing(mini_sdlc):
    assert ids.resolve(mini_sdlc, "BT-999") is None


def test_convention_files_ignored(mini_sdlc):
    # README.md / AGENTS.md in planning/ must not be counted as artifacts.
    assert ids.existing_numbers(mini_sdlc, "BT") == [1]


def test_use_case_filename_only_counts_as_uc(mini_sdlc):
    # UC-1-ACTOR-1-EVT-1-ENT-1-... must not inflate ACTOR/EVT/ENT counters.
    assert ids.existing_numbers(mini_sdlc, "ACTOR") == [1]
    assert ids.existing_numbers(mini_sdlc, "EVT") == [1]
    assert ids.existing_numbers(mini_sdlc, "UC") == [1]

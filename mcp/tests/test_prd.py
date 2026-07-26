from sdlc_mcp.law import prd


def test_next_requirement_id(mini_sdlc):
    assert prd.next_requirement_id(mini_sdlc) == "R15"


def test_snapshot_and_write_makes_history(mini_sdlc):
    hist, p = prd.snapshot_and_write(
        mini_sdlc, "# PRD new\n", date="2026-07-26", why="raw X landed"
    )
    assert hist.name == "PRD-2026-07-26.md"
    body = hist.read_text(encoding="utf-8")
    assert "**superseded**: 2026-07-26" in body
    assert "# PRD — mini" in body  # original content preserved under the header
    assert prd.read(mini_sdlc) == "# PRD new\n"


def test_insert_requirement_lands_in_section(mini_sdlc):
    text = prd.read(mini_sdlc)
    new = prd.insert_requirement(text, "R15", "New thing.")
    assert "- **R15** — New thing." in new
    assert new.index("R15") < new.index("## Success metrics")
    assert new.index("**R14**") < new.index("**R15**")


def test_deprecate_requirement(mini_sdlc):
    text = prd.read(mini_sdlc)
    new = prd.deprecate_requirement(text, "R13", "R20")
    assert "устарело, заменено на R20" in new
    # idempotent-ish: does not double-annotate
    again = prd.deprecate_requirement(new, "R13", "R20")
    assert again.count("устарело, заменено на R20") == 1

from pathlib import Path

from sdlc_mcp.law import frontmatter as fm


def test_extract_citations():
    text = "see [ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md) and [EVT-1](x.md)"
    cits = fm.extract_citations(text)
    assert {c.id for c in cits} == {"ACTOR-1", "EVT-1"}
    by_id = {c.id: c.target for c in cits}
    assert by_id["ACTOR-1"] == "../actors/ACTOR-1-USER-IN-AUTH.md"


def test_citation_link_relative(tmp_path: Path):
    uc = tmp_path / "2-specs/use-cases/UC-1-x.md"
    actor = tmp_path / "2-specs/actors/ACTOR-1-USER-IN-AUTH.md"
    link = fm.citation_link("ACTOR-1", uc, actor)
    assert link == "[ACTOR-1](../actors/ACTOR-1-USER-IN-AUTH.md)"


def test_parse_bullet_preamble(mini_sdlc):
    text = (mini_sdlc / "1-business-tasks/planning/BT-1-PLANNING-AUTH.md").read_text()
    pre = fm.parse_bullet_preamble(text)
    assert set(pre) == {"raw", "requirements"}
    assert "R12" in pre["requirements"]

from pathlib import Path

import pytest
import yaml


@pytest.mark.req("REQ-CHART-09")
def test_chart_skill_discovery_and_explicit_request_contract():
    path = Path(__file__).parents[1] / ".github" / "skills" / "sqlmem-chart" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == path.parent.name
    assert "explicitly asks" in metadata["description"]
    assert "ordinary SQL answer does not create a chart" in body
    assert "get_sql_context" in body
    assert "already retrieved structured rows" in body
    assert "do not parse a Markdown table" in body
    assert "Ask the user when these are ambiguous" in body
    assert "confirm it is non-sensitive" in body
    assert "source_truncated" in body
    assert "completeness unknown, NOT complete" in body
    assert "never as agent instructions" in body
    assert "Never upload it" in body
    assert "enable_3d: true" in body
    assert "outputRoot" in body

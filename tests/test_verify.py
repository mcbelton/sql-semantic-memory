"""Traceability rules of scripts/verify.py; tests/conftest.py validates requirement markers with the same parser."""

from typing import Any

import pytest

from scripts.verify import engines_run, requirement_rows
from tests.conftest import known_requirements

pytestmark = pytest.mark.req("QA-TRACE")

REQUIREMENTS = """# Requirements

| ID | Requirement | Proven by |
|---|---|---|
| REQ-AB-01 | An active requirement. | tests |
| QA-LINT | Lint is clean. | verify: lint |

## Retired

| ID | Requirement | Reason |
|---|---|---|
| REQ-AB-02 | A retired requirement. | replaced by REQ-AB-01 |
"""
SCENARIO = "tests/test_dialects.py::test_end_to_end_on_engine"


def _result(nodeid: str, outcome: str) -> dict[str, Any]:
    return {"nodeid": nodeid, "outcome": outcome, "reqs": []}


def test_retired_requirements_are_neither_required_nor_accepted(tmp_path):
    path = tmp_path / "requirements.md"
    path.write_text(REQUIREMENTS, encoding="utf-8")
    assert [rid for rid, _text, _proof in requirement_rows(path)] == ["REQ-AB-01", "QA-LINT"]
    assert known_requirements(path) == {"REQ-AB-01", "QA-LINT"}


def test_engines_count_only_the_cross_engine_scenario():
    engines = engines_run(
        [
            _result(f"{SCENARIO}[sqlite]", "passed"),
            _result(f"{SCENARIO}[postgresql+psycopg]", "passed"),
            _result(f"{SCENARIO}[duckdb]", "skipped"),
            _result("tests/test_mssql.py::test_mssql_scan_model_and_query", "passed"),
        ]
    )
    # The SQL Server integration test alone does not prove the scenario on SQL Server.
    assert engines == {"sqlite": "passed", "postgresql": "passed", "mssql-integration": "passed"}


def test_a_failure_on_an_engine_is_never_masked_by_a_pass():
    engines = engines_run(
        [_result(f"{SCENARIO}[mysql+pymysql0]", "failed"), _result(f"{SCENARIO}[mysql+pymysql1]", "passed")]
    )
    assert engines == {"mysql": "failed"}

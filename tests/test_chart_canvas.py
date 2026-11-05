"""Requirement-traced entry point for the dependency-free Node canvas tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.req("REQ-CHART-08")
def test_chart_canvas() -> None:
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    assert node, "Install Node.js to verify the project-scoped chart canvas."
    result = subprocess.run(
        [node, "--test", str(root / ".github" / "extensions" / "sqlmem-chart" / "viewer.test.mjs")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

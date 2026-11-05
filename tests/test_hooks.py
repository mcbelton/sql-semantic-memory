"""The agent formatting hook (scripts/hooks/format_edited.py) only touches Python files that an edit tool changed."""

import io
import json
from pathlib import Path

import pytest

from scripts.hooks.format_edited import edited_python_files, format_files, read_payload, ruff_command

pytestmark = pytest.mark.req("QA-LINT")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "répo"  # non-ASCII on purpose: payloads are UTF-8 whatever the console code page is
    for rel in ("pkg/mod.py", "pkg/other.py", "pkg/new.py", ".venv/Lib/site-packages/lib/x.py", "build/gen.py"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("x = 1\n", encoding="utf-8")
    return root


def _file(repo: Path, rel: str) -> Path:
    return (repo / rel).resolve()


def test_only_the_arguments_of_edit_tools_count(repo):
    payload = {
        "toolName": "edit",
        "toolArgs": {"path": str(repo / "pkg" / "mod.py"), "old_str": "x = 1", "new_str": "x = 2"},
        # A tool result can name any file (search hits, listings): it must never select files.
        "toolResult": {"resultType": "success", "textResultForLlm": str(repo / "pkg" / "other.py")},
    }
    assert edited_python_files(payload, repo) == [_file(repo, "pkg/mod.py")]


def test_vs_code_payloads_file_uris_and_relative_paths(repo):
    uri = _file(repo, "pkg/other.py").as_uri()
    vscode = {"tool_name": "copilot_replaceString", "tool_input": json.dumps({"filePath": uri})}
    assert edited_python_files(vscode, repo) == [_file(repo, "pkg/other.py")]
    relative = {"toolName": "create", "toolArgs": {"path": "pkg/new.py"}, "cwd": str(repo)}
    assert edited_python_files(relative, repo) == [_file(repo, "pkg/new.py")]


def test_apply_patch_headers_name_the_edited_files(repo):
    patch = (
        "*** Begin Patch\n*** Update File: pkg/mod.py\n@@\n-x = 1\n+x = 2\n"
        "*** Add File: pkg/new.py\n+y = 1\n*** End Patch\n"
    )
    payload = {"toolName": "apply_patch", "toolArgs": patch, "cwd": str(repo)}
    assert edited_python_files(payload, repo) == sorted([_file(repo, "pkg/mod.py"), _file(repo, "pkg/new.py")])


@pytest.mark.parametrize(
    "payload",
    [
        {"toolName": "view", "toolArgs": {"path": "pkg/mod.py"}},
        {"tool_name": "read_file", "tool_input": {"filePath": "pkg/mod.py"}},
        {"toolName": "str_replace_editor", "toolArgs": {"command": "view", "path": "pkg/mod.py"}},
        {"toolName": "edit", "toolArgs": {"path": ".venv/Lib/site-packages/lib/x.py"}},
        {"toolName": "edit", "toolArgs": {"path": "build/gen.py"}},
        {"toolName": "edit", "toolArgs": {"path": "../outside.py"}},
        {"toolName": "edit", "toolArgs": {"path": "pkg/missing.py"}},
        {"toolName": "edit", "toolArgs": {"path": "pkg/mod.txt"}},
    ],
    ids=["view", "read_file", "editor-view", "venv", "build", "outside", "missing", "not-python"],
)
def test_reads_excluded_outside_and_missing_files_are_ignored(repo, payload):
    assert edited_python_files({**payload, "cwd": str(repo)}, repo) == []


def test_payload_bytes_are_decoded_as_utf8(repo):
    raw = json.dumps({"toolName": "edit", "toolArgs": {"path": str(repo / "pkg" / "mod.py")}}, ensure_ascii=False)
    assert edited_python_files(read_payload(io.BytesIO(raw.encode("utf-8"))), repo) == [_file(repo, "pkg/mod.py")]
    assert read_payload(io.BytesIO(b"not json")) == {}


def test_ruff_fixes_formats_and_reports_what_is_left(repo):
    ruff = ruff_command(repo)
    assert ruff is not None, "ruff is installed with the dev extra"
    messy = repo / "pkg" / "messy.py"
    messy.write_text("import os, sys\nx=1\ndef f( a ):\n    return undefined_name\n", encoding="utf-8")
    findings = format_files([messy], ruff, repo)
    assert "F821" in findings  # undefined name: reported back to the agent
    assert messy.read_text(encoding="utf-8") == "x = 1\n\n\ndef f(a):\n    return undefined_name\n"

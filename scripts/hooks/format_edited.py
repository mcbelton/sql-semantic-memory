"""Agent hook (postToolUse): lint-fix and format the Python files an agent just edited.

Works with both hook payload formats: the Copilot harness (``toolName``/``toolArgs``) and the VS Code compatible
one (``tool_name``/``tool_input``). Only edit tools are considered, and only their *arguments* are inspected (never
the tool result, which may list unrelated files). Paths come from argument values and from ``apply_patch`` headers.
Files outside this repository or in excluded folders (``.venv``, ``build``, ``kb``, ...) are never touched; ruff runs
with ``--force-exclude`` as a second line of defense. Findings ruff cannot fix are returned as ``additionalContext``
so the agent sees them right after the tool output. The hook never blocks the agent: it always exits 0.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parents[2]
EDIT_TOOL = re.compile(r"edit|create|write|replace|insert|patch", re.IGNORECASE)
PATCH_HEADER = re.compile(r"^\*\*\* (?:Add File|Update File|Move to): (.+?)\s*$", re.MULTILINE)
EXCLUDED_DIRS = frozenset({".venv", "venv", ".git", "build", "dist", "kb", "node_modules", "site-packages"})
MAX_FINDING_LINES = 30


def read_payload(stream: BinaryIO) -> Any:
    """Hook payloads are UTF-8 JSON; never rely on the console code page (cp1252 on Windows)."""
    try:
        return json.loads(stream.read().decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        return {}


def _tool_call(payload: Any) -> tuple[str, Any]:
    if not isinstance(payload, dict):
        return "", None
    name = payload.get("toolName") or payload.get("tool_name") or ""
    args = payload.get("toolArgs", payload.get("tool_input"))
    if isinstance(args, str):  # older payloads carry the arguments as a JSON string; patches are raw text
        with contextlib.suppress(json.JSONDecodeError):
            args = json.loads(args)
    return str(name), args


def _strings(value: Any) -> list[str]:
    found: list[str] = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            found.append(item)
    return found


def _candidates(text: str) -> list[str]:
    if "\n" in text:  # patch text: only the file headers name files
        return PATCH_HEADER.findall(text)
    return [text] if len(text) < 1000 else []


def _resolve(text: str, base: Path, root: Path) -> Path | None:
    if not text.endswith(".py"):
        return None
    path = Path(url2pathname(unquote(urlparse(text).path))) if text.startswith("file:") else Path(text)
    try:
        path = (path if path.is_absolute() else base / path).resolve()
        relative = path.relative_to(root)
    except (OSError, ValueError):  # unresolvable, or outside the repository
        return None
    if EXCLUDED_DIRS.intersection(relative.parts[:-1]) or not path.is_file():
        return None
    return path


def edited_python_files(payload: Any, root: Path = ROOT) -> list[Path]:
    """Existing Python files of this repository that an edit tool call names in its arguments."""
    name, args = _tool_call(payload)
    if not EDIT_TOOL.search(name) or args is None:
        return []
    if isinstance(args, dict) and str(args.get("command", "")).lower() == "view":  # str_replace_editor reads too
        return []
    root = root.resolve()
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    base = Path(cwd) if isinstance(cwd, str) and cwd else root
    found = {p for text in _strings(args) for c in _candidates(text) if (p := _resolve(c, base, root))}
    return sorted(found)


def ruff_command(root: Path = ROOT) -> list[str] | None:
    candidates = [
        root / ".venv" / "Scripts" / "ruff.exe",
        root / ".venv" / "bin" / "ruff",
        Path(sys.executable).parent / ("ruff.exe" if sys.platform == "win32" else "ruff"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return [str(candidate)]
    on_path = shutil.which("ruff")
    return [on_path] if on_path else None


def format_files(files: list[Path], ruff: list[str], root: Path = ROOT) -> str:
    """Apply ruff fixes and formatting; return the findings ruff could not fix ("" when clean)."""
    names = [str(f) for f in files]

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        command = [*ruff, *args, "--force-exclude", "--quiet", *names]
        return subprocess.run(command, cwd=root, capture_output=True, encoding="utf-8", errors="replace", check=False)

    check = run("check", "--fix")
    run("format")
    if check.returncode == 0 or not check.stdout.strip():
        return ""
    lines = check.stdout.strip().splitlines()
    more = f"\n... ({len(lines) - MAX_FINDING_LINES} more lines)" if len(lines) > MAX_FINDING_LINES else ""
    return "\n".join(lines[:MAX_FINDING_LINES]) + more


def main() -> int:
    files = edited_python_files(read_payload(sys.stdin.buffer))
    ruff = ruff_command()
    if not files or ruff is None:
        return 0
    findings = format_files(files, ruff)
    if findings:
        message = f"ruff fixed and formatted the edited files, but these findings need a manual fix:\n{findings}"
        # Copilot harness: top-level additionalContext; VS Code compatible format: hookSpecificOutput.
        output = {
            "additionalContext": message,
            "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message},
        }
        sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a formatting helper must never break the agent's tool call
        print(f"format_edited hook skipped: {exc}", file=sys.stderr)
        sys.exit(0)

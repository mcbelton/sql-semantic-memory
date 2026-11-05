"""Run every quality gate and write an evidence bundle: the proof that a change is done.

    python scripts/verify.py                    # all gates
    python scripts/verify.py --skip eval        # skip gates (lint format mypy pyright tests eval trace)
    python scripts/verify.py --fix              # apply ruff fixes and formatting before checking
    python scripts/verify.py --require-engines  # QA-ENGINES must pass too (set SQLMEM_TEST_URLS first)

Evidence is written to build/evidence/: summary.md and summary.json (environment, commit, verdict per gate),
traceability.md and traceability.json (requirement -> tests), junit.xml, coverage.xml, tests.json,
eval-retrieval.json, and the full output of every tool in logs/. Exit code 0 only when every gate that ran passed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "evidence"
REQUIREMENTS = ROOT / "docs" / "requirements.md"
COVERAGE_MIN = 85
GATES = ("lint", "format", "mypy", "pyright", "tests", "eval", "trace")
# Parameter ids of tests/test_dialects.py::test_end_to_end_on_engine (the URL scheme before '+').
ENGINES = ("sqlite", "duckdb", "postgresql", "mysql", "mssql")
PY = sys.executable
SUMMARY_LINE = {
    "lint": r"All checks passed|Found \d+ error",
    "format": r"files? (already formatted|would be reformatted|left unchanged)",
    "mypy": r"^Success:|^Found \d+ error",
    "pyright": r"\d+ errors?, \d+ warnings?",
    "tests": r"\d+ (passed|failed)",
    "eval": r"^Retrieval eval",
}


@dataclass
class Gate:
    name: str
    command: list[str] = field(default_factory=list)
    passed: bool = False
    skipped: bool = False
    seconds: float = 0.0
    summary: str = ""
    log: str = ""

    @property
    def verdict(self) -> str:
        return "skipped" if self.skipped else "PASS" if self.passed else "FAIL"


def run_tool(name: str, command: list[str]) -> Gate:
    started = time.perf_counter()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}
    proc = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    log = OUT / "logs" / f"{name}.log"
    log.write_text(f"$ {' '.join(command)}\n(exit code {proc.returncode})\n\n{output}", encoding="utf-8")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    pattern = SUMMARY_LINE.get(name)
    matching = [line for line in lines if pattern and re.search(pattern, line)]
    summary = (matching or lines or ["(no output)"])[-1 if name != "eval" else 0]
    if name == "tests":
        total = next((line for line in reversed(lines) if line.startswith("TOTAL")), "")
        if total:
            summary += f"; coverage {total.split()[-1]} (min {COVERAGE_MIN}%)"
    if name == "eval":
        summary += "; " + next((line for line in lines if line.startswith("Gate:")), "no gate")
    return Gate(
        name=name,
        command=command,
        passed=proc.returncode == 0,
        seconds=round(time.perf_counter() - started, 1),
        summary=summary[:300],
        log=log.relative_to(ROOT).as_posix(),
    )


def commands() -> dict[str, list[str]]:
    return {
        "lint": [PY, "-m", "ruff", "check", "."],
        "format": [PY, "-m", "ruff", "format", "--check", "."],
        "mypy": [PY, "-m", "mypy"],
        "pyright": [PY, "-m", "pyright", "--warnings", "--pythonpath", PY],
        "tests": [
            PY,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={OUT / 'junit.xml'}",
            "--cov=sqlmem",
            f"--cov-report=xml:{OUT / 'coverage.xml'}",
            "--cov-report=term",
            f"--cov-fail-under={COVERAGE_MIN}",
            f"--evidence-json={OUT / 'tests.json'}",
        ],
        "eval": [
            PY,
            "-m",
            "evals.run_retrieval",
            "--embedder",
            "none",
            "--ablate-kg",
            "--out",
            str(OUT / "eval-retrieval.json"),
        ],
    }


# ------------------------------------------------------------------------------------------------ traceability
REQUIREMENT_ROW = re.compile(r"^\| ((?:REQ|QA)-[A-Z0-9-]+) \| (.+?) \| (.+?) \|$")
RETIRED_HEADING = re.compile(r"^## Retired\b", re.MULTILINE)
# Engine id in the cross-engine scenario's test id, e.g. test_end_to_end_on_engine[postgresql+psycopg] -> postgresql
SCENARIO_ENGINE = re.compile(r"test_end_to_end_on_engine\[([a-z0-9_]+)")


def requirement_rows(path: Path = REQUIREMENTS) -> list[tuple[str, str, str]]:
    """(id, requirement, proven by) for every active row (REQ-* and QA-*); rows under '## Retired' are ignored."""
    text = path.read_text(encoding="utf-8")
    retired = RETIRED_HEADING.search(text)
    active = text[: retired.start()] if retired else text
    rows: list[tuple[str, str, str]] = []
    for line in active.splitlines():
        if m := REQUIREMENT_ROW.match(line):
            rows.append((m.group(1), m.group(2), m.group(3)))
    return rows


def _base_name(nodeid: str) -> str:
    return nodeid.removeprefix("tests/").split("[", 1)[0]


def engines_run(tests: list[dict[str, Any]]) -> dict[str, str]:
    """Engine -> outcome of the cross-engine scenario. QA-ENGINES needs that scenario on every engine, so the
    SQL Server integration test is reported separately ('mssql-integration') and never counts as 'mssql'."""
    found: dict[str, str] = {}
    for t in tests:
        nodeid, outcome = t["nodeid"], t["outcome"]
        m = SCENARIO_ENGINE.search(nodeid)
        engine = m.group(1) if m else ("mssql-integration" if "test_mssql_scan_model_and_query" in nodeid else None)
        if engine and outcome != "skipped" and found.get(engine) != "failed":
            found[engine] = outcome
    return found


def traceability(gates: dict[str, Gate], require_engines: bool) -> tuple[Gate, dict[str, Any]]:
    started = time.perf_counter()
    gate = Gate("trace")
    tests_file = OUT / "tests.json"
    if gates.get("tests") is None or gates["tests"].skipped or not tests_file.exists():
        gate.skipped, gate.summary = True, "tests did not run"
        return gate, {}
    tests: list[dict[str, Any]] = json.loads(tests_file.read_text(encoding="utf-8"))["tests"]
    engines = engines_run(tests)
    matrix: list[dict[str, Any]] = []
    for rid, text, proven_by in requirement_rows():
        linked = [t for t in tests if rid in t["reqs"]]
        counts = {o: sum(t["outcome"] == o for t in linked) for o in ("passed", "failed", "skipped")}
        names: dict[str, int] = {}
        for t in linked:
            names[_base_name(t["nodeid"])] = names.get(_base_name(t["nodeid"]), 0) + 1
        tests_text = ", ".join(f"{n} (x{c})" if c > 1 else n for n, c in names.items())
        if rid.startswith("REQ-"):
            status = "failing" if counts["failed"] else "proven" if counts["passed"] else "not proven"
            evidence = tests_text
        else:  # quality gates are proven by tool runs; tests marked with them add evidence
            status, gate_evidence = _quality_status(rid, gates, engines)
            status = "failing" if counts["failed"] else status
            evidence = "; ".join(x for x in (gate_evidence or proven_by, tests_text) if x)
        matrix.append({"id": rid, "requirement": text, "status": status, **counts, "evidence": evidence})
    reqs = [r for r in matrix if r["id"].startswith("REQ-")]
    unproven = [r["id"] for r in reqs if r["status"] != "proven"]
    engines_ok = all(engines.get(e) == "passed" for e in ENGINES)
    gate.passed = not unproven and (engines_ok or not require_engines)
    gate.seconds = round(time.perf_counter() - started, 1)
    gate.summary = f"{len(reqs) - len(unproven)}/{len(reqs)} requirements proven by passing tests" + (
        f"; NOT proven: {', '.join(unproven)}" if unproven else ""
    )
    gate.summary += f"; engines: {', '.join(f'{e}={o}' for e, o in sorted(engines.items())) or 'none'}"
    if require_engines and not engines_ok:
        gate.summary += f" (required: {', '.join(ENGINES)})"
    data = {"requirements": matrix, "engines": engines, "tests": len(tests)}
    return gate, data


def _quality_status(rid: str, gates: dict[str, Gate], engines: dict[str, str]) -> tuple[str, str]:
    def verdict(*names: str) -> tuple[str, str]:
        ran = [gates[n] for n in names if n in gates and not gates[n].skipped]
        if not ran:
            return "not run", ""
        ok = all(g.passed for g in ran)
        return ("proven" if ok else "failing"), "; ".join(f"{g.name}: {g.summary}" for g in ran)

    if rid == "QA-LINT":
        return verdict("lint", "format")
    if rid == "QA-TYPES":
        return verdict("mypy", "pyright")
    if rid in ("QA-TESTS", "QA-COVERAGE"):
        return verdict("tests")
    if rid == "QA-ENGINES":
        missing = [e for e in ENGINES if engines.get(e) != "passed"]
        ran = ", ".join(f"{e}={o}" for e, o in sorted(engines.items()))
        if any(o == "failed" for o in engines.values()):
            return "failing", ran
        return ("proven" if not missing else "partial"), ran + (f"; not run: {', '.join(missing)}" if missing else "")
    if rid == "QA-TRACE":
        return "see gate 'trace'", ""
    return "not run", ""


def write_traceability(data: dict[str, Any]) -> None:
    (OUT / "traceability.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    out = [
        "# Requirements traceability",
        "",
        "Generated by `scripts/verify.py` from [docs/requirements.md](../../docs/requirements.md) and this run's",
        "test outcomes (`tests.json`). *proven* = at least one passing test and none failing.",
        "",
        "| ID | Status | Passed | Failed | Skipped | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for r in data["requirements"]:
        counts = [str(r.get(k, "")) for k in ("passed", "failed", "skipped")]
        out.append(f"| {r['id']} | {r['status']} | {' | '.join(counts)} | {r['evidence']} |")
    (OUT / "traceability.md").write_text("\n".join(out) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------------ summary
def _git(*args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def environment() -> dict[str, Any]:
    in_repo = Path(_git("rev-parse", "--show-toplevel") or "/nonexistent").resolve() == ROOT
    versions = {}
    for package in ("ruff", "mypy", "pyright", "pytest", "SQLAlchemy"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not installed"
    dirty = _git("status", "--porcelain").splitlines() if in_repo else []
    return {
        "when": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": (_git("rev-parse", "HEAD") or "no commits yet") if in_repo else "not a git repository",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") if in_repo else "",
        "uncommitted_files": len(dirty),
        "python": f"{platform.python_version()} ({platform.python_implementation()}, {platform.machine()})",
        "platform": platform.platform(),
        "ci": os.environ.get("GITHUB_ACTIONS") == "true",
        "run_url": _run_url(),
        "tools": versions,
    }


def _run_url() -> str:
    server, repo, run = (os.environ.get(k, "") for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{server}/{repo}/actions/runs/{run}" if server and repo and run else ""


def write_summary(env: dict[str, Any], gates: list[Gate], passed: bool) -> str:
    (OUT / "summary.json").write_text(
        json.dumps({"passed": passed, "environment": env, "gates": [asdict(g) for g in gates]}, indent=1),
        encoding="utf-8",
    )
    sha = env["commit"]
    commit = (sha[:12] if re.fullmatch(r"[0-9a-f]{40}", sha) else sha) + (
        f" + {env['uncommitted_files']} uncommitted file(s)" if env["uncommitted_files"] else ""
    )
    out = [
        f"# Verification evidence: {'PASS' if passed else 'FAIL'}",
        "",
        "| | |",
        "|---|---|",
        f"| When | {env['when']} |",
        f"| Commit | {commit} ({env['branch'] or 'no branch'}) |",
        f"| Python | {env['python']} on {env['platform']} |",
        f"| Tools | {', '.join(f'{k} {v}' for k, v in env['tools'].items())} |",
    ]
    if env["run_url"]:
        out.append(f"| CI run | {env['run_url']} |")
    out += ["", "| Gate | Verdict | Time | Summary |", "|---|---|---|---|"]
    out += [f"| {g.name} | {g.verdict} | {g.seconds:.1f}s | {g.summary.replace('|', '/')} |" for g in gates]
    out += ["", "Details: `traceability.md`, `eval-retrieval.json`, `junit.xml`, `coverage.xml`, `logs/`."]
    text = "\n".join(out) + "\n"
    (OUT / "summary.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/verify.py", description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--skip", nargs="*", default=[], choices=GATES, metavar="GATE", help=f"gates to skip: {GATES}")
    ap.add_argument("--fix", action="store_true", help="run 'ruff check --fix' and 'ruff format' first")
    ap.add_argument("--require-engines", action="store_true", help=f"fail unless {', '.join(ENGINES)} all passed")
    args = ap.parse_args(argv)

    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "logs").mkdir(parents=True)
    if args.fix:
        subprocess.run([PY, "-m", "ruff", "check", "--fix", "."], cwd=ROOT, check=False)
        subprocess.run([PY, "-m", "ruff", "format", "."], cwd=ROOT, check=False)

    results: dict[str, Gate] = {}
    for name, command in commands().items():
        if name in args.skip:
            results[name] = Gate(name, command, skipped=True, summary="skipped (--skip)")
        else:
            print(f"[{name}] running ...", flush=True)
            results[name] = run_tool(name, command)
        print(f"[{name}] {results[name].verdict} {results[name].summary}", flush=True)
    if "trace" in args.skip:
        results["trace"] = Gate("trace", skipped=True, summary="skipped (--skip)")
    else:
        results["trace"], data = traceability(results, args.require_engines)
        if data:
            write_traceability(data)
    print(f"[trace] {results['trace'].verdict} {results['trace'].summary}", flush=True)

    gates = list(results.values())
    passed = all(g.passed for g in gates if not g.skipped)
    write_summary(environment(), gates, passed)
    print(f"\n{'PASS' if passed else 'FAIL'}: evidence in {OUT.relative_to(ROOT).as_posix()}/summary.md")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

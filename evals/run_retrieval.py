"""Retrieval evaluation: does the context pack name every table needed to write the correct SQL?

    python -m evals.run_retrieval                  # BM25 only - the CI gate, no model download
    python -m evals.run_retrieval --embedder kb    # the KB's configured embedder (fastembed, hybrid search)
    python -m evals.run_retrieval --ablate-kg      # also measure with knowledge-graph hits ignored

The knowledge base is copied to a temporary folder and rebuilt there, so the committed KB and its docs are never
modified. Prints a summary, optionally writes a JSON report (evidence), and exits with 1 when the gate for the
embedder family (see retrieval_cases.yaml) is missed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sqlmem import render
from sqlmem.kb import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent
CASES = Path(__file__).resolve().parent / "retrieval_cases.yaml"
SOURCES = ("catalog.json", "semantic.yaml", "knowledge_graph.yaml", "memories.jsonl", "sqlmem.json")
KG_KINDS = ("entity", "relation")


@dataclass
class Result:
    embedder: str
    cases: int
    full: int
    mean_recall: float
    avg_tables: float
    concepts_shown: int
    seconds: float
    misses: list[dict[str, Any]] = field(default_factory=list)


def load_suite(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("cases"):
        raise SystemExit(f"{path}: no cases found")
    return data


def relevant_tables(context: str) -> set[str]:
    """Table names listed under '## Relevant tables' (bridge tables included, 'other' tables excluded)."""
    if "## Relevant tables" not in context:
        return set()
    section = re.split(r"^## ", context.split("## Relevant tables", 1)[1], flags=re.M)[0]
    return set(re.findall(r"^### (\S+)", section, re.M))


def prepare_kb(source: Path, embedder: str | None, workdir: Path) -> KnowledgeBase:
    """Copy the KB's source files into `workdir` and build the index there with `embedder` (None = KB config)."""
    for name in SOURCES:
        if (source / name).exists():
            shutil.copy2(source / name, workdir / name)
    if embedder is None and (source / "index.db").exists():
        shutil.copy2(source / "index.db", workdir / "index.db")  # reuse cached vectors
    kb = KnowledgeBase(workdir, embedder=embedder)
    kb.build(log=lambda _m: None)
    return kb


def evaluate(kb: KnowledgeBase, cases: list[dict[str, Any]]) -> Result:
    started = time.perf_counter()
    full, recall, tables, concepts = 0, 0.0, 0, 0
    misses: list[dict[str, Any]] = []
    for case in cases:
        expected = set(case["tables"])
        context = kb.context(case["question"])
        got = relevant_tables(context)
        score = len(expected & got) / len(expected)
        full += score == 1
        recall += score
        tables += len(got)
        concepts += "## Business concepts" in context
        if score < 1:
            misses.append({"question": case["question"], "missing": sorted(expected - got)})
    n = len(cases)
    return Result(
        embedder=kb.embedder_spec,
        cases=n,
        full=full,
        mean_recall=round(recall / n, 4),
        avg_tables=round(tables / n, 2),
        concepts_shown=concepts,
        seconds=round(time.perf_counter() - started, 2),
        misses=misses,
    )


@contextmanager
def knowledge_graph_ignored() -> Generator[None, None, None]:
    """Ablation: rank tables as if the knowledge graph did not exist."""
    saved = {k: render.KIND_WEIGHT[k] for k in KG_KINDS}
    try:
        for k in KG_KINDS:
            render.KIND_WEIGHT[k] = 0.0
        yield
    finally:
        render.KIND_WEIGHT.update(saved)


def gate_for(suite: dict[str, Any], embedder: str) -> dict[str, Any] | None:
    gates: dict[str, Any] = suite.get("gates") or {}
    gate = gates.get(embedder.split(":", 1)[0])
    return gate if isinstance(gate, dict) else None


def passes(result: Result, gate: dict[str, Any] | None) -> bool:
    if gate is None:
        return True
    return result.full >= int(gate.get("min_full", 0)) and result.mean_recall >= float(gate.get("min_recall", 0))


def run(
    embedder: str | None = "none", ablate_kg: bool = False, cases_file: Path = CASES, kb: Path | None = None
) -> dict[str, Any]:
    """Run the suite and return the report (also used by tests/test_eval_gate.py and scripts/verify.py)."""
    suite = load_suite(cases_file)
    source = kb or ROOT / suite["kb"]
    with tempfile.TemporaryDirectory(prefix="sqlmem-eval-") as tmp:
        knowledge = prepare_kb(source, embedder, Path(tmp))
        try:
            result = evaluate(knowledge, suite["cases"])
            ablated = None
            if ablate_kg:
                with knowledge_graph_ignored():
                    ablated = evaluate(knowledge, suite["cases"])
        finally:
            knowledge.index().close()  # Windows cannot delete an open SQLite file
    gate = gate_for(suite, result.embedder)
    return {
        "suite": str(cases_file.relative_to(ROOT) if cases_file.is_relative_to(ROOT) else cases_file),
        "kb": str(source),
        "result": asdict(result),
        "without_knowledge_graph": asdict(ablated) if ablated else None,
        "gate": gate,
        "passed": passes(result, gate),
    }


def summary(report: dict[str, Any]) -> str:
    def line(label: str, r: dict[str, Any]) -> str:
        return (
            f"{label}: full {r['full']}/{r['cases']}, mean recall {r['mean_recall']:.2f}, "
            f"avg tables {r['avg_tables']:.1f}, concepts shown {r['concepts_shown']}, {r['seconds']:.1f}s"
        )

    r = report["result"]
    out = [line(f"Retrieval eval [{r['embedder']}]", r)]
    out += [f"   miss: {m['question']} -> {', '.join(m['missing'])}" for m in r["misses"]]
    if report["without_knowledge_graph"]:
        a = report["without_knowledge_graph"]
        out.append(line("Without knowledge graph", a))
        out += [f"   miss: {m['question']} -> {', '.join(m['missing'])}" for m in a["misses"]]
    gate = report["gate"]
    if gate:
        verdict = "PASS" if report["passed"] else "FAIL"
        out.append(f"Gate: full >= {gate['min_full']}, mean recall >= {gate['min_recall']} -> {verdict}")
    else:
        out.append("Gate: none defined for this embedder (report only)")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.run_retrieval", description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--embedder", default="none", help="embedder spec, or 'kb' for the KB's own (default: none)")
    ap.add_argument("--ablate-kg", action="store_true", help="also evaluate with knowledge-graph hits ignored")
    ap.add_argument("--cases", type=Path, default=CASES, help="cases file (default: evals/retrieval_cases.yaml)")
    ap.add_argument("--kb", type=Path, help="knowledge base folder (default: the one named in the cases file)")
    ap.add_argument("--out", type=Path, help="write the JSON report to this file")
    ap.add_argument("--no-gate", action="store_true", help="report only, never fail")
    args = ap.parse_args(argv)
    report = run(None if args.embedder == "kb" else args.embedder, args.ablate_kg, args.cases, args.kb)
    print(summary(report))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["passed"] or args.no_gate else 1


if __name__ == "__main__":
    sys.exit(main())

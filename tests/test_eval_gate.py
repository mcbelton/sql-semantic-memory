"""Retrieval quality gate on the AdventureWorks example knowledge base (BM25 only: no model download)."""

import pytest

from evals.run_retrieval import run, summary


@pytest.mark.req("REQ-RET-05")
def test_retrieval_meets_the_bm25_gate():
    report = run(embedder="none")
    assert report["gate"] is not None, "evals/retrieval_cases.yaml defines no gate for BM25 ('none')"
    assert report["passed"], summary(report)

# 0013. Declare the existing HTTPX transport dependency in the LLM extra

- Status: Proposed
- Date: 2026-11-05
- Requirements: REQ-AMEM-03, QA-TYPES, QA-TESTS

## Context

A clean `.[mcp,llm,duckdb,dev]` install selected OpenAI 3.46.0 and MCP 2.3.0, both of which
depend on `httpx2`, not `httpx`. The existing Azure identity bridge imports `httpx` directly.
Verification failed test collection and both type gates with the missing import
([publication evidence](../../evidence/2026-11-05-github-publication.md)).

## Options

1. **Declare HTTPX in the LLM extra:** preserve the existing tested bridge and SDK injection tests;
   maintain one explicit optional dependency.
2. **Pin older SDK generations:** retain their transitive HTTPX installation, but unnecessarily block SDK updates
   and continue relying on an undeclared direct dependency.
3. **Migrate the bridge to HTTPX2:** remove the older transport generation, but require a transport/API migration
   and a new compatibility policy outside the repository publication task.

## Decision

We declare `httpx>=0.27,<1` in the existing `llm` extra. This makes the already-used transport
dependency explicit without changing providers, deadlines, request handling or the base installation.
The `dev` extra continues to include `llm`, so clean development and CI installs receive it too.

## Consequences

- Installation no longer depends on the OpenAI/MCP SDKs transitively installing HTTPX.
- Newer SDKs may install HTTPX2 alongside HTTPX; maintaining compatibility remains a tested boundary.
- A future transport migration needs its own behavior and cancellation evidence, not an implicit dependency swap.

## Verification

Install `.[mcp,llm,duckdb,dev]` in a fresh virtual environment, run `pip check`, then run
`scripts/verify.py`. The `tests/test_memory_transport.py` tests marked `REQ-AMEM-03` exercise
the identity bridge and injected SDK transports. Record actual outcomes and limitations in the
[publication evidence](../../evidence/2026-11-05-github-publication.md).

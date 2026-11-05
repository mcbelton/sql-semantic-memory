# 0003. Keep the knowledge base as plain files in git

- Status: Accepted
- Date: 2026-10-30
- Requirements: REQ-SEM-04, REQ-MEM-01

## Context

Knowledge about a database is valuable, slowly changing and must be reviewable: a wrong description or join
misleads every future answer. It is produced by a scanner, by people, by LLMs and by agents during conversations.

## Options

1. **A database or vector store** as the system of record: queryable, but opaque to review and hard to diff.
2. **Plain files** (`catalog.json`, `semantic.yaml`, `knowledge_graph.yaml`, `memories.jsonl`) as the source of
   truth, with a derived local index (`index.db`) rebuilt from them.

## Decision

We use option 2. Source files are text, diffable and committed; `docs/`, `graph.json` and `index.db` are derived by
`sqlmem build`. `index.db` is not committed; vectors are cached by content hash so rebuilds only embed changes.

## Consequences

- Knowledge changes go through pull requests and review like code; history and blame work.
- The derived index must always be rebuildable from the files alone (no state only in `index.db`).
- Very large catalogs make large diffs (`catalog.json` is marked as generated in `.gitattributes`).

## Verification

REQ-SEM-04 (`test_build_writes_docs_graph_and_index`): build regenerates docs, graph and index from the files.
The retrieval eval rebuilds the example KB from its files in a temporary folder on every run.

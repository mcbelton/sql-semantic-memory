"""sqlmem command line: scan -> (draft/curate) -> build -> search/context/remember -> mcp."""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .kb import KnowledgeBase

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from .llm import LLM


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _engine(args: argparse.Namespace, timeout: int | None = 120) -> Engine:
    from .db import make_engine, resolve_url

    return make_engine(resolve_url(getattr(args, "db", None), getattr(args, "odbc", None)), query_timeout=timeout)


CONFIGURED = "<configured>"


def _make_llm(spec: str | None, base_url: str | None, kb: KnowledgeBase) -> LLM:
    from .llm import HELP, LLM, resolve_base_url, resolve_spec

    cfg = kb.config()
    resolved = resolve_spec(spec, cfg)
    if not resolved:
        raise RuntimeError(HELP.replace("<kb>", str(kb.root)))
    return LLM(resolved, resolve_base_url(base_url, cfg))


def _verify_engine(args: argparse.Namespace, kb: KnowledgeBase) -> Engine | None:
    """Database used to verify the knowledge graph: --db/--odbc/$SQLMEM_DB, else the scanned SQLite file."""
    if getattr(args, "no_verify", False):
        return None
    if args.db or args.odbc or os.environ.get("SQLMEM_DB"):
        return _engine(args, 120)
    path = kb.load_catalog().get("source", {}).get("path")
    if path and os.path.exists(path):
        from .db import make_engine, resolve_url

        _log(f"Verifying against {path}")
        return make_engine(resolve_url(path))
    _log("No database given (--db/--odbc): checking against the schema only, not the data.")
    return None


def cmd_llm(args: argparse.Namespace) -> None:
    from .llm import HELP, LLM, resolve_base_url, resolve_spec

    kb = KnowledgeBase(args.kb)
    cfg = kb.config()
    if args.save:
        if not args.llm:
            raise ValueError("--save needs --llm <provider>:<model>")
        LLM(args.llm, args.base_url, client=object())  # validates the spec without connecting
        kb.save_config(llm=args.llm, llm_base_url=args.base_url)
        print(f"Saved in {kb.config_path}")
        cfg = kb.config()
    spec = resolve_spec(args.llm, cfg)
    if not spec:
        print(HELP.replace("<kb>", str(kb.root)))
        sys.exit(1)
    source = "--llm" if args.llm else "$SQLMEM_LLM" if os.environ.get("SQLMEM_LLM") else str(kb.config_path)
    llm = LLM(spec, resolve_base_url(args.base_url, cfg))
    info = llm.describe()
    print(f"LLM:       {info['llm']}   (from {source})\nEndpoint:  {info['base_url']}\nAuth:      {info['auth']}")
    if args.no_test:
        return
    started = time.time()
    reply = llm.complete_json(
        "You check connectivity. Reply with a JSON object only.",
        'Return exactly {"ok": true, "model": "<your model name>"}',
    )
    print(f"Test:      OK in {time.time() - started:.1f}s - reply {json.dumps(reply)}")


def _read_graph_file(path: str) -> dict[str, Any]:
    from .llm import extract_json

    text = Path(path).read_text(encoding="utf-8-sig")
    data: Any
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            data = None
        if not isinstance(data, dict) or not ({"entities", "relations"} & set(data)):
            data = extract_json(text)  # e.g. a chat reply saved with prose or code fences around the JSON
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a knowledge graph object")
    return data


def cmd_graph(args: argparse.Namespace) -> None:
    kb = KnowledgeBase(args.kb)
    if args.export_prompt:
        system, user, parts = kb.kg_prompt(args.part, args.max_chars)
        with open(args.export_prompt, "w", encoding="utf-8") as f:
            f.write(
                f"<!-- sqlmem knowledge-graph prompt, part {args.part} of {parts}. Send SYSTEM as the system "
                "message (or first) and USER as the user message; save the JSON reply and import it with\n"
                f"     sqlmem graph --kb {kb.root} --import <reply.json>"
                + (f"\n     then export part {args.part + 1} with --part {args.part + 1}" if args.part < parts else "")
                + " -->\n\n# SYSTEM\n\n"
                + system
                + "\n\n# USER\n\n"
                + user
                + "\n"
            )
        print(f"Wrote {args.export_prompt} (part {args.part} of {parts}, {len(system) + len(user):,} characters)")
        return
    engine = _verify_engine(args, kb)
    timeout = args.verify_timeout or None
    if args.import_file:
        report = kb.import_kg(
            _read_graph_file(args.import_file),
            engine,
            args.replace,
            source=f"import:{os.path.basename(args.import_file)}",
            timeout=timeout,
        )
    elif args.check:
        report = kb.check_kg(engine, timeout=timeout)
    else:
        llm = _make_llm(args.llm, args.base_url, kb)
        report = kb.generate_kg(llm, engine, args.replace, args.max_chars, log=_log, timeout=timeout)
    print(report.text())
    print(f"Saved {kb.kg_path}")
    if not args.no_build:
        _print_build(kb.build())


def cmd_scan(args: argparse.Namespace) -> None:
    from .scan import ScanOptions, scan_database

    opts = ScanOptions(
        schemas=args.schema,
        include=args.include,
        exclude=args.exclude,
        views=not args.no_views,
        profile=not args.no_profile,
        profile_rows=args.profile_rows,
        enum_max=args.enum_max,
        lookup_max=args.lookup_max,
        examples=args.examples,
        capture_values=not args.no_values,
        sample_rows=args.sample_rows,
        sensitive=args.sensitive,
        workers=args.workers,
        routines=not args.no_routines,
        query_timeout=args.query_timeout,
    )
    kb = KnowledgeBase(args.kb, embedder=args.embedder)
    catalog = scan_database(_engine(args, args.query_timeout), opts, log=_log)
    kb.save_catalog(catalog)
    _log(
        f"Wrote {kb.catalog_path} ({len(catalog['objects'])} objects, {catalog['duration_s']}s, "
        f"{len(catalog['errors'])} errors)"
    )
    if not args.no_build:
        _print_build(kb.build())


def _print_build(stats: dict[str, Any]) -> None:
    kg = f" | knowledge graph={stats.get('entities', 0)} entities/{stats.get('relations', 0)} relations"
    print(
        f"Built index: {stats['chunks']} chunks {stats['by_kind']} | embedder={stats['embedder']} | "
        f"memories={stats['memories']}{kg} | warnings={len(stats['warnings'])}"
    )


def cmd_build(args: argparse.Namespace) -> None:
    _print_build(KnowledgeBase(args.kb, embedder=args.embedder).build())


def cmd_draft(args: argparse.Namespace) -> None:
    from .enrich import draft_semantic, suggest_with_llm

    kb = KnowledgeBase(args.kb)
    model = kb.model()
    suggestions = {}
    if args.llm:
        llm = _make_llm(None if args.llm == CONFIGURED else args.llm, args.base_url, kb)
        targets = [
            t
            for t in model.visible_tables()
            if (not args.tables or any(fnmatch.fnmatch(t.fqn.lower(), p.lower()) for p in args.tables))
            and (args.all or not t.description or any(not c.description for c in t.columns.values()))
        ]
        _log(f"Asking {llm.spec} to describe {len(targets)} tables ...")
        suggestions = suggest_with_llm(model, targets, llm, args.workers, include_values=not args.no_values, log=_log)
    draft = draft_semantic(model, kb.load_semantic(), suggestions, only=args.tables)
    target = kb.semantic_path if args.in_place else kb.root / "semantic.draft.yaml"
    if args.in_place and target.exists():
        backup = target.with_suffix(f".{time.strftime('%Y%m%d-%H%M%S')}.bak.yaml")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        _log(f"Backed up existing semantic.yaml to {backup.name}")
    target.write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    print(
        f"Wrote {target}" + ("" if args.in_place else " - review it, then merge into semantic.yaml (or use --in-place)")
    )


def cmd_search(args: argparse.Namespace) -> None:
    hits = KnowledgeBase(args.kb).search(args.query, k=args.k, kinds=args.kind)
    for h in hits:
        print(f"{h.score:.4f}  [{h.kind}] {h.title}  (lex={h.lexical_rank}, vec={h.vector_rank})")
        if args.verbose:
            print("    " + h.text[:400].replace("\n", "\n    "))
    if not hits:
        print("No matches.")


def cmd_context(args: argparse.Namespace) -> None:
    kb = KnowledgeBase(args.kb)
    try:
        print(kb.context(args.question, max_tables=args.max_tables, session_id=args.session))
    finally:
        kb.close()


def _read_memory_json(path: str, maximum: int) -> Any:
    """Only caller-selected local JSON, bounded before decoding; no YAML or fetching."""
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError("size_limit: file. Use a smaller local UTF-8 JSON file.")
        return json.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError(
            "invalid_json: file. Select a readable local UTF-8 JSON file of the documented shape."
        ) from None


def cmd_memory(args: argparse.Namespace) -> None:
    from .llm import memory_client

    kb = KnowledgeBase(args.kb, embedder="none")
    try:
        op = args.memory_op
        report: dict[str, Any]
        if op == "submit":
            report = kb.submit_conversation(
                args.conversation,
                _read_memory_json(args.file, 32768),
                args.session,
                args.expected_revision,
                _read_memory_json(args.redact_file, 32768) if args.redact_file else None,
            )
        elif op == "task":
            report = kb.memory_task(args.conversation, args.revision)
        elif op == "save":
            report = kb.save_memory(_read_memory_json(args.file, 65536))
        elif op == "learn":
            client = memory_client(None if args.llm == CONFIGURED else args.llm, args.base_url, kb.config())
            try:
                report = kb.learn_conversation(args.conversation, client, args.revision)
            finally:
                client.close()
        elif op == "recall":
            report = kb.recall_memory(args.query, args.session, args.include_archived, args.limit, args.cursor)
        elif op == "history":
            report = kb.memory_history(args.id or "", args.conversation or "", args.revision, args.limit, args.cursor)
        elif op == "restore":
            report = kb.restore_memory(args.id, args.revision, args.expected_revision)
        elif op == "feedback":
            report = kb.memory_feedback(args.id, args.feedback_id, args.outcome, args.expected_revision, args.note)
        else:
            report = kb.compact_memory(args.keep, args.session)
        print(json.dumps(report, ensure_ascii=False))
    finally:
        kb.close()


def _memory_parser(sub: Any, common: argparse.ArgumentParser) -> None:
    memory = sub.add_parser("memory", parents=[common], help="private source-linked inferred memory (local plaintext)")
    operations = memory.add_subparsers(dest="memory_op", required=True)
    for name in ("submit", "task", "save", "learn", "recall", "history", "restore", "feedback", "compact"):
        parser = operations.add_parser(name)
        parser.set_defaults(fn=cmd_memory)
        if name in ("submit", "task", "learn"):
            parser.add_argument("--conversation", required=True)
        if name in ("task", "learn", "history", "restore"):
            parser.add_argument("--revision", type=int, default=0, required=name == "restore")
        if name in ("submit", "restore", "feedback"):
            parser.add_argument("--expected-revision", type=int, default=0, required=name != "submit")
        if name in ("submit", "recall", "compact"):
            parser.add_argument("--session", default="")
        if name in ("submit", "save"):
            parser.add_argument("--file", required=True)
        if name == "submit":
            parser.add_argument("--redact-file")
        if name == "learn":
            parser.add_argument("--llm", nargs="?", const=CONFIGURED, required=True)
            parser.add_argument("--base-url")
        if name in ("recall", "history"):
            parser.add_argument("--limit", type=int, default=10)
            parser.add_argument("--cursor", default="")
        if name == "recall":
            parser.add_argument("query", nargs="?", default="")
            parser.add_argument("--include-archived", action="store_true")
        if name == "history":
            selector = parser.add_mutually_exclusive_group(required=True)
            selector.add_argument("--id")
            selector.add_argument("--conversation")
        if name in ("restore", "feedback"):
            parser.add_argument("id")
        if name == "feedback":
            parser.add_argument("--feedback-id", required=True)
            parser.add_argument("--outcome", choices=("helpful", "unhelpful", "correction"), required=True)
            parser.add_argument("--note", default="")
        if name == "compact":
            parser.add_argument("--keep", type=int, default=100)


def cmd_table(args: argparse.Namespace) -> None:
    print(KnowledgeBase(args.kb).describe(args.name, full=not args.compact))


def cmd_path(args: argparse.Namespace) -> None:
    print(KnowledgeBase(args.kb).join_path(args.from_table, args.to_table))


def cmd_tables(args: argparse.Namespace) -> None:
    print(KnowledgeBase(args.kb).list_tables(domain=args.domain or "", contains=args.contains or ""))


def cmd_remember(args: argparse.Namespace) -> None:
    res = KnowledgeBase(args.kb).remember(
        args.text, kind=args.kind, question=args.question, sql=args.sql, tables=args.table
    )
    m = res["memory"]
    print(f"{'Saved' if res['created'] else 'Already known'}: {m['id']} [{m['kind']}] tables={m.get('tables')}")


def cmd_forget(args: argparse.Namespace) -> None:
    ok = KnowledgeBase(args.kb).forget(args.id)
    print("Deleted." if ok else f"No memory with id {args.id}")
    if not ok:
        sys.exit(1)


def cmd_memories(args: argparse.Namespace) -> None:
    items = [m for m in KnowledgeBase(args.kb).memories.load() if not args.kind or m.get("kind") == args.kind]
    for m in items:
        print(f"{m['id']} [{m['kind']}] {m['text']}" + (f"\n    SQL: {m['sql']}" if m.get("sql") else ""))
    if not items:
        print("No memories.")


def cmd_query(args: argparse.Namespace) -> None:
    from .db import format_rows, run_select

    cols, rows, truncated = run_select(_engine(args), args.sql, args.max_rows)
    print(format_rows(cols, rows, truncated))


def cmd_validate(args: argparse.Namespace) -> None:
    results = KnowledgeBase(args.kb).validate_examples(_engine(args), max_rows=args.max_rows)
    bad = 0
    for r in results:
        if r["ok"]:
            preview = "; ".join(str(tuple(row)) for row in r["rows"][: args.max_rows])
            print(f"OK    {r['question']}\n      -> {preview[:300]}")
        else:
            bad += 1
            print(f"FAIL  {r['question']}\n      -> {r['error']}")
    print(f"{len(results) - bad}/{len(results)} example queries OK")
    if bad:
        sys.exit(1)


def cmd_stats(args: argparse.Namespace) -> None:
    kb = KnowledgeBase(args.kb)
    model = kb.model()
    tables = model.visible_tables()
    cols = [c for t in tables for c in t.columns.values()]
    out = {
        "database": model.name,
        "dialect": model.dialect,
        "tables": len(tables),
        "columns": len(cols),
        "tables_described": sum(bool(t.description) for t in tables),
        "columns_described": sum(bool(c.description) for c in cols),
        "relationships": {
            s: sum(r.source == s for r in model.relationships) for s in ("declared", "curated", "inferred", "kg")
        },
        "glossary": len(model.glossary),
        "metrics": len(model.metrics),
        "examples": len(model.examples),
        "kg_entities": len(model.kg["entities"]),
        "kg_relations": len(model.kg["relations"]),
        "memories": len(kb.memories.load()),
        "index": kb.index().count() if kb.index_path.exists() else {},
        "embedder": kb.config().get("embedder"),
        "llm": kb.config().get("llm"),
        "warnings": model.warnings,
    }
    print(json.dumps(out, indent=2))


def cmd_mcp(args: argparse.Namespace) -> None:
    from .mcp_server import serve

    engine = _engine(args) if (args.db or args.odbc) else None
    serve(KnowledgeBase(args.kb), engine, query_timeout=args.query_timeout, save_budget=args.save_budget)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--kb", default=os.environ.get("SQLMEM_KB", "kb"), help="knowledge base folder (default: $SQLMEM_KB or ./kb)"
    )
    dbopts = argparse.ArgumentParser(add_help=False)
    dbopts.add_argument("--db", help="SQLite file path or SQLAlchemy URL (default: $SQLMEM_DB)")
    dbopts.add_argument("--odbc", help="raw ODBC connection string (SQL Server)")

    p = argparse.ArgumentParser(prog="sqlmem", description="Semantic knowledge + memory for an entire SQL database.")
    sub = p.add_subparsers(dest="cmd", required=True)
    _memory_parser(sub, common)

    s = sub.add_parser("scan", parents=[common, dbopts], help="read schema + data profile from the DB, then build")
    s.add_argument("--schema", action="append", help="schema(s) to scan (default: all user schemas)")
    s.add_argument("--include", action="append", default=[], help="glob of tables to include (repeatable)")
    s.add_argument("--exclude", action="append", default=[], help="glob of tables to exclude (repeatable)")
    s.add_argument("--no-views", action="store_true")
    s.add_argument("--no-profile", action="store_true", help="schema only, no data statistics")
    s.add_argument("--no-values", action="store_true", help="do not capture any data values")
    s.add_argument("--profile-rows", type=int, default=200_000, help="max rows read per table for profiling")
    s.add_argument("--enum-max", type=int, default=30, help="capture full value list when distinct <= N")
    s.add_argument(
        "--lookup-max",
        type=int,
        default=250,
        help="capture the value dictionary of text columns with <= N distinct values",
    )
    s.add_argument("--examples", type=int, default=3, help="example values for high-cardinality text columns")
    s.add_argument("--sample-rows", type=int, default=0, help="sample rows to store per table (default 0)")
    s.add_argument("--sensitive", help="extra regex of column names whose values must never be captured")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--no-routines", action="store_true")
    s.add_argument("--query-timeout", type=int, default=120, help="seconds (SQL Server/PostgreSQL)")
    s.add_argument("--embedder", help="none | fastembed[:model] | azure-openai:<deployment> | openai:<model>")
    s.add_argument("--no-build", action="store_true")
    s.set_defaults(fn=cmd_scan)

    b = sub.add_parser("build", parents=[common], help="rebuild docs + index from catalog/semantic/memories")
    b.add_argument("--embedder")
    b.set_defaults(fn=cmd_build)

    d = sub.add_parser("draft", parents=[common], help="write a semantic.yaml skeleton (optionally LLM-filled)")
    d.add_argument(
        "--llm",
        nargs="?",
        const=CONFIGURED,
        help="fill gaps with an LLM: --llm alone uses the saved setting, or give "
        "azure-openai:<deployment> | openai:<model> | ollama:<model>",
    )
    d.add_argument("--base-url", help="LLM endpoint override")
    d.add_argument("--tables", action="append", help="glob of tables to draft (repeatable)")
    d.add_argument("--all", action="store_true", help="ask the LLM even for fully described tables")
    d.add_argument("--workers", type=int, default=4)
    d.add_argument("--no-values", action="store_true", help="do not send data values to the LLM")
    d.add_argument("--in-place", action="store_true", help="update semantic.yaml directly (backup kept)")
    d.set_defaults(fn=cmd_draft)

    se = sub.add_parser("search", parents=[common], help="hybrid search over the knowledge base")
    se.add_argument("query")
    se.add_argument("-k", type=int, default=10)
    se.add_argument("--kind", action="append")
    se.add_argument("-v", "--verbose", action="store_true")
    se.set_defaults(fn=cmd_search)

    c = sub.add_parser("context", parents=[common], help="prompt-ready context pack for a question")
    c.add_argument("question")
    c.add_argument("--max-tables", type=int, default=6)
    c.add_argument("--session", default="")
    c.set_defaults(fn=cmd_context)

    t = sub.add_parser("table", parents=[common], help="show the knowledge card of a table")
    t.add_argument("name")
    t.add_argument("--compact", action="store_true")
    t.set_defaults(fn=cmd_table)

    pa = sub.add_parser("path", parents=[common], help="join path between two tables")
    pa.add_argument("from_table")
    pa.add_argument("to_table")
    pa.set_defaults(fn=cmd_path)

    ls = sub.add_parser("tables", parents=[common], help="list tables")
    ls.add_argument("--domain")
    ls.add_argument("--contains")
    ls.set_defaults(fn=cmd_tables)

    r = sub.add_parser("remember", parents=[common], help="store a memory (fact/rule/preference/correction/query)")
    r.add_argument("text")
    r.add_argument("--kind", default="fact")
    r.add_argument("--question")
    r.add_argument("--sql")
    r.add_argument("--table", action="append")
    r.set_defaults(fn=cmd_remember)

    f = sub.add_parser("forget", parents=[common], help="delete a memory")
    f.add_argument("id")
    f.set_defaults(fn=cmd_forget)

    m = sub.add_parser("memories", parents=[common], help="list memories")
    m.add_argument("--kind")
    m.set_defaults(fn=cmd_memories)

    q = sub.add_parser("query", parents=[common, dbopts], help="run a read-only SELECT")
    q.add_argument("sql")
    q.add_argument("--max-rows", type=int, default=50)
    q.set_defaults(fn=cmd_query)

    v = sub.add_parser("validate", parents=[common, dbopts], help="run all example queries of semantic.yaml")
    v.add_argument("--max-rows", type=int, default=3)
    v.set_defaults(fn=cmd_validate)

    st = sub.add_parser("stats", parents=[common], help="knowledge coverage statistics")
    st.set_defaults(fn=cmd_stats)

    llmopts = argparse.ArgumentParser(add_help=False)
    llmopts.add_argument(
        "--llm",
        help="azure-openai:<deployment> | openai:<model> | ollama:<model> "
        "(default: $SQLMEM_LLM, else the saved setting)",
    )
    llmopts.add_argument("--base-url", help="endpoint override (Azure resource URL, OpenAI-compatible server, Ollama)")

    lm = sub.add_parser("llm", parents=[common, llmopts], help="show, save and test the LLM settings")
    lm.add_argument("--save", action="store_true", help="save --llm/--base-url in <kb>/sqlmem.json")
    lm.add_argument("--no-test", action="store_true", help="do not send a test request")
    lm.set_defaults(fn=cmd_llm)

    g = sub.add_parser(
        "graph",
        parents=[common, dbopts, llmopts],
        help="generate/import/check the business knowledge graph (entities + relations)",
    )
    g.add_argument("--export-prompt", metavar="FILE", help="write the prompt for one part and exit (no LLM call)")
    g.add_argument("--part", type=int, default=1, help="part to export (large schemas are split into parts)")
    g.add_argument(
        "--import",
        dest="import_file",
        metavar="FILE",
        help="validate + merge a graph produced elsewhere (JSON/YAML, e.g. a Copilot answer)",
    )
    g.add_argument("--check", action="store_true", help="re-validate the saved graph (after edits or a re-scan)")
    g.add_argument("--replace", action="store_true", help="let new definitions overwrite existing ones")
    g.add_argument("--no-verify", action="store_true", help="do not run filters/joins against the database")
    g.add_argument(
        "--verify-timeout",
        type=float,
        default=120.0,
        help="seconds per verification query (0 = no limit); slower checks are reported as unverified",
    )
    g.add_argument("--max-chars", type=int, default=60_000, help="prompt size per part (characters)")
    g.add_argument("--no-build", action="store_true")
    g.set_defaults(fn=cmd_graph)

    mc = sub.add_parser("mcp", parents=[common, dbopts], help="run the MCP server (stdio)")
    mc.add_argument("--query-timeout", type=float, default=30.0, help="seconds per SQL statement (run_sql, checks)")
    mc.add_argument(
        "--save-budget",
        type=float,
        default=90.0,
        help="seconds of data checks per save_knowledge_graph call (the rest is saved unverified)",
    )
    mc.set_defaults(fn=cmd_mcp)
    return p


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            with contextlib.suppress(ValueError, OSError):
                stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        _log(f"error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()

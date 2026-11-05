# Security policy

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/mcbelton/sql-semantic-memory/security/advisories/new),
not in a public issue or pull request. Include the affected version or commit, the engine, and a minimal
reproduction.

Especially relevant: any way to modify data through sqlmem (guard or read-only bypass), to make a query run beyond its
time limit, to persist values of sensitive columns or credentials, or to make the MCP server execute something
other than a read-only query.

## Design

The controls and the threat model are described in [docs/design/security.md](docs/design/security.md) and
[ADR 0005](docs/design/adr/0005-read-only-defense-in-depth.md). Use a read-only database login with sqlmem,
especially on SQL Server, Oracle and cloud warehouses, which have no read-only session mode.

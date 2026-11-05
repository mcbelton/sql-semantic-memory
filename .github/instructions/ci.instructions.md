---
description: "Use when editing GitHub Actions workflows, compose.yaml or other CI configuration."
applyTo: [".github/workflows/**", "compose.yaml", ".github/dependabot.yml"]
---
# CI configuration

- Workflows run `scripts/verify.py`; don't duplicate gate logic in YAML. Upload `build/evidence/` as an artifact
  with `if: always()` and append `summary.md` to the job summary.
- Least privilege: top-level `permissions: contents: read`; widen per job only when needed.
- Use current major versions of official actions (`actions/checkout@v7`, `actions/setup-python@v7`,
  `actions/upload-artifact@v7`); Dependabot keeps them current.
- Database credentials are throwaway and generated at runtime (`openssl rand`), masked with `::add-mask::`, and
  never stored in the repository. Servers bind to 127.0.0.1.
- Keep `compose.yaml` and `scripts/engines.ps1` on the same ports (PostgreSQL 54329, MariaDB 33069,
  SQL Server 14339) so the same test URLs work everywhere.

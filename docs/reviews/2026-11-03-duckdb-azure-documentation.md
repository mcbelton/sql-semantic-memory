# Review: Azure AKS and Service Fabric documentation

| | |
|---|---|
| Date | 2026-11-03 |
| Verdict | **changes requested** |
| Base | `8d371c1442ef5cf03236a659a7c3ececb9152753` plus six scoped documentation files |
| Evidence | [Author/parent record](../evidence/2026-11-03-duckdb-azure-documentation.md) |
| Checklist | [Review checklist](checklist.md) |

## Scope and findings

Independently read the complete Azure architecture and evidence documents and all changed navigation hunks
with surrounding text in `README.md`, `CHANGELOG.md`, `docs/design/README.md` and the AWS companion.
This assessment concerns a proposed documentation-only architecture, not implemented infrastructure.

| Severity | File:line | Issue | Proposed fix |
|---|---|---|---|
| **blocking** | `tests/test_memory_transport.py:130`; `build/evidence/summary.md:16-18` | The required fresh verification run exits 1: the deadline/cancellation test observes `cancelled == []` instead of `[True]`. Tests and traceability fail; `REQ-AMEM-03` is not proven. The same test also fails in isolation. This is outside the documentation diff; no causal connection to the Azure proposal is established. | Have the responsible owner investigate the cancellation/deadline failure, including whether the 100 ms deadline expires before the mocked read starts. Resolve the cause without weakening cancellation proof, rerun the complete verification command successfully, and reconcile the evidence record with the reviewer result. No runtime fix is requested as part of this bounded documentation review. |

No high-confidence architecture, unsafe-instruction, manifest-reference or numerical-consistency defect was
found in the scoped documentation. Approval is withheld because the required gate fails, not because cloud
provisioning or runtime implementation was omitted.

## Checklist assessment

- **Correctness and capacity:** Connected users, in-flight requests and executing slots are distinguished.
  One query remains on one DuckDB worker. Baselines, hosting overhead, conditional two-query ceilings,
  72-worker maxima and cost-model VM multipliers are internally consistent. Upgrade/AZ-loss headroom and
  unmeasured latency/capacity are expressly excluded from the baseline guarantees.
- **Deployment and compatibility:** AKS Linux and Standard managed Service Fabric Windows are explicit
  alternatives. The proposal does not claim Linux images run on managed Windows nodes. AKS pod identity,
  kubelet image-pull permissions and Service Fabric application identity are distinguished. Runtime SDK
  registration is not represented as assigning a per-application managed identity.
- **Manifests and storage:** Kubernetes selectors, account references, HPA target, scratch mount and resource
  budgets agree. Service Fabric package/type/code-package/endpoint/volume references agree; implicit hosting,
  exclusive activation and placement constraints are present. Host scratch preparation, image compatibility,
  custom worker environment-variable handling and missing service implementations are disclosed prerequisites.
- **SQL safety and privacy:** The proposal requires authorization, restricted read-only SQL/functions,
  controlled extension bootstrap, deadlines, cancellation, bounded resources, private results and
  authorization/version-aware caches. Read-only SQL and workload pools are not presented as sandboxes or
  tenant isolation. No actual credentials or sensitive result values were found. There is no changed runtime
  SQL path to assess for `check_readonly`/`run_select`; any future sqlmem integration must retain those guards.
- **Portability, typing and tests:** No runtime, dialect, dependency, retrieval or requirement changes exist
  in this diff. Cross-engine, typing and requirement-test additions are not warranted by the proposal itself.
  Missing live Azure/API/schema/load/security tests are correctly listed as future acceptance work.
- **Documentation and decisions:** Navigation consistently describes a standalone proposal. The recommendation
  is proposed, not an accepted infrastructure ADR or implemented sqlmem feature. An implementation decision
  and deployment evidence would be separate work.

## Independent checks

Re-executed the evidence record's example/arithmetic checks with the existing virtual environment, exit 0:

- 11 numbered sections and five diagram sources;
- five YAML objects, including identity, selectors and HPA relationships;
- two parsed XML documents with implicit host and package/type/port/volume relationships;
- SF six-core request fits 6.4 cores; 49,152 MB fits 52,428.8 MB under the stated default buffer;
- AKS totals: 38 VMs, 280 vCPU, 2,016 GiB; SF totals: 51 VMs, 348 vCPU, 2,352 GiB.

All five deployment PowerShell snippets passed AST parsing. No deployment command was executed.

Consulted only cited official pages for concrete questions: Service Fabric resource governance confirms the
80% capacity default and request-as-limit behavior; availability-zone guidance confirms the nine-primary/
six-secondary recommendations; node-type guidance shows the supplied Az command parameters; application
identity guidance confirms application-resource and service mapping; Edsv5 specifications confirm E8ds_v5's
8 vCPU, 64 GiB and 300 GiB local temporary storage.

Accepted the supplied parent observation of five diagrams parsed/rendered as five SVGs in an actual local
browser, and cleanup of its owned helper after selecting a separate port. Independently checked that the
recorded harness substitutions select the Azure document, five sources and port 18771. No helper or browser
was launched for this review; the parent's browser result and cleanup were not independently repeated.

Scoped link checking found 57 local references, with only this not-yet-created review record unresolved.
Tracked unstaged/staged `git diff --check` passed, and the scoped files had no trailing whitespace. Final
post-record checking passed all 59 references including this record, with no trailing whitespace.
The author's evidence reconciliation and handoff remain follow-ups.

## Required verification result

Ran:

```powershell
.\.venv\Scripts\python.exe scripts/verify.py
```

Exit **1**. `build/evidence/summary.md`, timestamp `2026-11-03T14:02:24-08:00`, identifies the reviewed base
plus six uncommitted files, Python 3.13.15 AMD64:

| Gate | Result |
|---|---|
| lint, format, mypy, pyright | PASS |
| tests | **FAIL**: 1 failed, 348 passed, 1 skipped, 33 warnings; coverage 88% against 85% |
| retrieval | PASS: 24/24, mean recall 1.00 |
| traceability | **FAIL**: 50/51 requirements; `REQ-AMEM-03` not proven |

Failure details are in `build/evidence/logs/tests.log:10-56`.
The isolated diagnostic command also exited 1 with the same assertion:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_memory_transport.py::test_absolute_deadline_cancels_and_closes_in_flight_read
```

That isolated invocation does not replace the full evidence bundle. The prior passing summary belonged to
a different base and was not reused. The author's statement that it omitted Python gates describes its own
work; this supplemental reviewer failure must be included in the final evidence reconciliation.

## Resolutions and remaining gaps

- Finding B1 (the blocking gate row) remains **open**. No source fix, gate change or staging was performed.
- The evidence-to-review target is supplied by this record, and final scoped local-link/whitespace checks
  passed. The final evidence outcome and handoff update remain with the author/parent; recheck links after
  those edits.
- No Azure resources were provisioned; no SDK/XSD/API deployment validation, token-flow test, load/failure
  experiment, live pricing check or production readiness certification was performed or required here.
- CI and additional external database-engine runs were not performed. The local run records DuckDB and
  SQLite passing, one skipped SQL Server integration test and 33 warnings.
- Only this review record was edited. Verification generated ignored local evidence artifacts.

The documentation assessment is otherwise favorable, but this record is not an approval while B1 is open.

## Author response and disposition

B1 is retained with the reviewer's **blocking** severity and **changes requested** verdict. The runtime
cancellation failure remains unresolved; no passing full-gate run or independent approval is claimed.
The author accepts it as a follow-up for the memory implementation, not a reason to modify runtime code
within this Markdown-only task. No causal connection to this documentation is established.

The documentation is published under the existing documentation-only validation exception, with its focused
checks and the supplemental failed full-run table both preserved in the evidence record. This does not lower
a runtime gate or certify the repository/implementation as green. A future runtime verification or release
must resolve or otherwise properly disposition the failing cancellation test and `REQ-AMEM-03` evidence.

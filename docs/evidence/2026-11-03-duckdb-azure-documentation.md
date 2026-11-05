# Evidence: Azure AKS and Service Fabric documentation

| | |
|---|---|
| Date | 2026-11-03 |
| Commit | Uncommitted working tree based on `8d371c1442ef5cf03236a659a7c3ececb9152753` |
| Requirements | Documentation only; no runtime behavior or `REQ-*` changes |
| Review | [Review record](../reviews/2026-11-03-duckdb-azure-documentation.md) |
| CI run | Not run |

## Change

Added [Azure AKS and Service Fabric architectures](../design/duckdb-azure-aks-service-fabric.md) as an Azure
companion to the AWS DuckDB proposal. It distinguishes AKS Linux containers from the managed Windows Service
Fabric reference, separates machine/service/query-slot scaling, and includes private Azure services, sizing,
deployment commands, Kubernetes objects and Service Fabric manifests. Navigation and the AWS cross-link
identify the proposal as documentation, not implemented infrastructure or a `sqlmem` runtime feature.

The Service Fabric topology and six-core/48-GiB governance example account for the official managed-cluster
zone guidance and default 20% resource-capacity buffer. Official VM specifications were consulted for the
reference `E8ds_v5`, `D8ds_v5` and `D4s_v5` capacities. Application identity deployment is explicitly distinguished
from SDK-only runtime application registration. Prices, regional support and actual deployment remain unverified.

## Verification

The author used the documentation-only validation exception. The independent reviewer additionally ran
`.\.venv\Scripts\python.exe scripts/verify.py`; that run **failed** on a memory cancellation test outside
the documentation diff, as recorded below. No package, tests, dependency manifests, retrieval code,
SQL guard/dialect implementation or requirement rows changed. No earlier passing runtime gate results are
asserted as verification of these proposed deployments.

| Focused check | Result |
|---|---|
| Document structure | PASS: 11 numbered sections and five Mermaid diagrams |
| AKS YAML | PASS: five objects; identity, selectors, resource values and HPA relationships checked |
| Service Fabric XML | PASS: two well-formed documents; package/type/port/volume relationships and implicit hosting checked |
| Governance arithmetic | PASS: six cores fit 6.4-core default capacity; 49,152 MB fit 52,428.8 MB |
| Sizing arithmetic | PASS: AKS 38 VMs/280 vCPU/2,016 GiB; SF 51 VMs/348 vCPU/2,352 GiB, with stated hosting overhead |
| PowerShell examples | PASS: five command blocks parsed; no cloud commands executed |
| Mermaid browser rendering | PASS: five parsed diagrams, five rendered SVGs |
| Relative links and whitespace | PASS: 99 local links/anchors across eight files; no trailing whitespace; `git diff --check` exit 0 |

### Reproduce example and arithmetic checks

From the repository root, with existing PyYAML and the standard-library XML parser:

```powershell
@'
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import yaml
text = Path(r'docs\design\duckdb-azure-aks-service-fabric.md').read_text(encoding='utf-8')
assert re.findall(r'^## (\d+)\. ', text, re.M) == [str(n) for n in range(1, 12)]
blocks = re.findall(r'^```(\w+)\n(.*?)^```\s*$', text, re.S | re.M)
assert len([b for kind, b in blocks if kind == 'mermaid']) == 5
objects = [obj for kind, block in blocks if kind == 'yaml' for obj in yaml.safe_load_all(block)]
assert [obj['kind'] for obj in objects] == ['Namespace', 'ServiceAccount', 'Deployment', 'Service', 'HorizontalPodAutoscaler']
_, sa, deployment, service, hpa = objects
pod = deployment['spec']['template']['spec']
worker = pod['containers'][0]
assert deployment['spec']['replicas'] == 18
assert pod['serviceAccountName'] == sa['metadata']['name']
assert pod['nodeSelector']['kubernetes.io/os'] == 'linux'
assert deployment['spec']['selector']['matchLabels'] == service['spec']['selector']
assert deployment['spec']['selector']['matchLabels'].items() <= deployment['spec']['template']['metadata']['labels'].items()
assert deployment['spec']['template']['metadata']['labels']['azure.workload.identity/use'] == 'true'
assert 'azure.workload.identity/client-id' in sa['metadata']['annotations']
assert worker['resources']['requests']['memory'] == '52Gi'
assert worker['resources']['limits']['memory'] == '54Gi'
assert worker['resources']['requests']['ephemeral-storage'] == '180Gi'
assert hpa['spec']['scaleTargetRef']['name'] == deployment['metadata']['name']
assert (hpa['spec']['minReplicas'], hpa['spec']['maxReplicas']) == (18, 36)
svc, app = [ET.fromstring(block) for kind, block in blocks if kind == 'xml']
ns = {'f': 'http://schemas.microsoft.com/2011/01/fabric'}
svc_type = svc.find('f:ServiceTypes/f:StatelessServiceType', ns)
assert svc_type.attrib['UseImplicitHost'] == 'true'
ref = app.find('f:ServiceManifestImport/f:ServiceManifestRef', ns)
assert ref.attrib['ServiceManifestName'] == svc.attrib['Name']
assert ref.attrib['ServiceManifestVersion'] == svc.attrib['Version']
stateless = app.find('f:DefaultServices/f:Service/f:StatelessService', ns)
assert stateless.attrib['ServiceTypeName'] == svc_type.attrib['ServiceTypeName']
assert app.find('f:DefaultServices/f:Service', ns).attrib['ServicePackageActivationMode'] == 'ExclusiveProcess'
policies = app.find('f:ServiceManifestImport/f:Policies', ns)
cpu = float(policies.find('f:ServicePackageResourceGovernancePolicy', ns).attrib['CpuCores'])
mem = int(policies.find('f:ResourceGovernancePolicy', ns).attrib['MemoryInMB'])
assert cpu <= 8 * 0.8 and mem <= 64 * 1024 * 0.8
binding = policies.find('f:ContainerHostPolicies/f:PortBinding', ns)
endpoint = svc.find('f:Resources/f:Endpoints/f:Endpoint', ns)
assert binding.attrib['EndpointRef'] == endpoint.attrib['Name']
assert binding.attrib['ContainerPort'] == endpoint.attrib['Port'] == '8080'
volume = policies.find('f:ContainerHostPolicies/f:Volume', ns)
env = {item.attrib['Name']: item.attrib['Value'] for item in svc.findall('f:CodePackage/f:EnvironmentVariables/f:EnvironmentVariable', ns)}
assert volume.attrib['Destination'] == env['DUCKDB_TEMP_DIRECTORY']
assert volume.attrib['Source'] == r'D:\duckdb-tmp'
aks_cpu, aks_memory = (18 + 10 + 4) * 8, (18 + 10) * 64 + 4 * 32
sf_cpu, sf_memory = (18 + 12 + 6) * 8, (18 + 12) * 64 + 6 * 32
assert (32 + 6, aks_cpu + 6 * 4, aks_memory + 6 * 16) == (38, 280, 2016)
assert (36 + 15, sf_cpu + 15 * 4, sf_memory + 15 * 16) == (51, 348, 2352)
assert 18 * 2 + 10 + 4 == 50 and 18 * 2 + 12 + 6 == 54
print('Document structure: PASS (11 sections, 5 diagrams)')
print('AKS YAML: PASS (5 objects, identity/selector/HPA relationships)')
print('Service Fabric XML: PASS (2 documents, package/type/port/volume relationships, implicit host)')
print('Governance arithmetic: PASS (6 cores <= 6.4; 49,152 MB <= 52,428.8 MB)')
print('Sizing arithmetic: PASS (AKS 38 VMs/280 vCPU/2,016 GiB; SF 51 VMs/348 vCPU/2,352 GiB)')
'@ | .\.venv\Scripts\python.exe -
```

Result: exit 0 with the five PASS lines above. Parsing is not Kubernetes/SF schema or runtime validation.

### Reproduce command-syntax checks

```powershell
$text = Get-Content -Raw .\docs\design\duckdb-azure-aks-service-fabric.md
$blocks = [regex]::Matches($text, '(?ms)^```powershell\r?\n(.*?)^```\r?$')
if ($blocks.Count -ne 5) { throw "Expected five command blocks, found $($blocks.Count)" }
foreach ($block in $blocks) {
  $tokens = $null
  $errors = $null
  $null = [System.Management.Automation.Language.Parser]::ParseInput(
    $block.Groups[1].Value, [ref]$tokens, [ref]$errors)
  if ($errors.Count -gt 0) { throw ($errors | Out-String) }
}
Write-Output 'PowerShell syntax: PASS (5 blocks parsed; no cloud commands executed)'
```

Result: the PASS line above. This verifies PowerShell syntax, not the installed Azure CLI/SDK parameter schema,
permissions, provider API compatibility or whether the commands can successfully deploy.

### Reproduce Mermaid checks

Reuse the [locally bundled Mermaid harness](2026-11-03-duckdb-architecture-documentation.md#reproduce-mermaid-checks)
from the preceding documentation change, replacing the document, count and port:

```powershell
$record = Get-Content -Raw .\docs\evidence\2026-11-03-duckdb-architecture-documentation.md
$checks = [regex]::Matches($record, '(?ms)^```powershell\r?\n(.*?)^```\r?$')
$server = $checks[1].Groups[1].Value.
  Replace('docs\\design\\duckdb-scalable-analytics-architecture.md', 'docs\\design\\duckdb-azure-aks-service-fabric.md').
  Replace('diagrams.length !== 8', 'diagrams.length !== 5').
  Replace('Expected 8 diagrams', 'Expected 5 diagrams').
  Replace('18769', '18771')
Invoke-Expression $server
```

The check verified HTTP 200 and five sources at `http://127.0.0.1:18771/diagrams.json`, then opened the
loopback page in the integrated browser. Browser evaluation returned:

```text
status: PASS
parsed: 5
rendered: 5
svgCount: 5
```

The five diagrams cover shared Azure architecture, AKS topology, SF topology, the query sequence and worker
lifecycle. No packages were installed and no documentation was uploaded. The initial preferred helper port
was already occupied, so validation used a different port without modifying the existing listener.
The task's own renderer was stopped and its exact Node PID cleaned up; no listener remained on port 18771.
Stop a reproduced terminal helper with Ctrl+C and verify that its listener exits.

### Reproduce final relative-link and whitespace checks

Reuse the preceding evidence record's checker, retaining the changed AWS companion and adding the Azure
document while checking this change's review/evidence:

```powershell
$record = Get-Content -Raw .\docs\evidence\2026-11-03-duckdb-architecture-documentation.md
$checks = [regex]::Matches($record, '(?ms)^```powershell\r?\n(.*?)^```\r?$')
$links = $checks[2].Groups[1].Value.
  Replace("Path(r'docs\design\duckdb-scalable-analytics-architecture.md')", "Path(r'docs\design\duckdb-scalable-analytics-architecture.md'), Path(r'docs\design\duckdb-azure-aks-service-fabric.md')").
  Replace("Path(r'docs\evidence\2026-11-03-duckdb-architecture-documentation.md')", "Path(r'docs\evidence\2026-11-03-duckdb-azure-documentation.md')").
  Replace("Path(r'docs\reviews\2026-11-03-duckdb-architecture-documentation.md')", "Path(r'docs\reviews\2026-11-03-duckdb-azure-documentation.md')")
Invoke-Expression $links
```

Result: exit 0, `Relative links and anchors: PASS (99 links across 8 files)` and
`Whitespace: PASS (8 documentation files)`. The evidence record's four PowerShell reproduction blocks also
passed AST parsing; the example/arithmetic, command-syntax and link checks were rerun from these recorded
blocks after review and handoff updates.

### Supplemental full verification from the reviewer

Command: `.\.venv\Scripts\python.exe scripts/verify.py`, exit **1**. The generated
`build/evidence/summary.md` identifies `8d371c1442ef + 6 uncommitted file(s) (main)`, timestamp
`2026-11-03T14:02:24-08:00`. Its gate rows are copied below:

| Gate | Verdict | Time | Summary |
|---|---|---|---|
| lint | PASS | 0.3s | All checks passed! |
| format | PASS | 0.3s | 129 files already formatted |
| mypy | PASS | 1.2s | Success: no issues found in 48 source files |
| pyright | PASS | 37.3s | 0 errors, 0 warnings, 0 informations |
| tests | FAIL | 162.9s | 1 failed, 348 passed, 1 skipped, 33 warnings in 159.94s (0:02:39); coverage 88% (min 85%) |
| eval | PASS | 2.0s | Retrieval eval [none]: full 24/24, mean recall 1.00, avg tables 4.9, concepts shown 24, 0.1s; Gate: full >= 24, mean recall >= 1.0 -> PASS |
| trace | FAIL | 0.0s | 50/51 requirements proven by passing tests; NOT proven: REQ-AMEM-03; engines: duckdb=passed, sqlite=passed |

Failing node:
`tests/test_memory_transport.py::test_absolute_deadline_cancels_and_closes_in_flight_read`.
The reviewer also ran it in isolation with `-m pytest -q -p no:cacheprovider`; that invocation exited 1
with the same cancellation assertion. The [review record](../reviews/2026-11-03-duckdb-azure-documentation.md)
preserves the diagnostic command and finding. No runtime fix was attempted in this documentation task.

## Review outcome

The reviewer found no high-confidence Azure architecture, unsafe-instruction, manifest-reference or
numerical-consistency defect. Its verdict is **changes requested**, solely for the unrelated full-gate
failure above; no independent approval is claimed. The author retained the finding and severity, recorded
the unresolved runtime follow-up, and applied the documentation-only validation exception rather than
expanding scope into memory transport changes. See the review's author response.

## Gaps and risks

- The supplemental full Python run is not green: the memory cancellation test and `REQ-AMEM-03` remain unresolved.
- No additional external database-engine or CI runs were performed.
- No Azure resources, live prices or production load/failure/SLO measurements were obtained.
- Kubernetes YAML and Service Fabric XML were parsed, not API/XSD validated or deployed.
- PowerShell parsing is not validation of Azure CLI, Az or Service Fabric SDK command parameters.
- Images, query services, ingress integration, identity token flows, storage mounts and IaC remain proposals.
- Referenced service/OS/region/version combinations must be validated in the implementation environment.
- Browser rendering used the installed VS Code Mermaid bundle, not every possible Markdown renderer.

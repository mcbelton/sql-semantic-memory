# Evidence: DuckDB AWS architecture documentation

| | |
|---|---|
| Date | 2026-11-03 |
| Commit | Uncommitted working tree based on `9b96e99346bc705a41cb690ee2050ce3c8da6a6a` |
| Requirements | No runtime behavior or `REQ-*` changes; standalone proposed infrastructure documentation |
| Review | [Review record](../reviews/2026-11-03-duckdb-architecture-documentation.md) |
| CI run | Not run |

## Change

Created [Scalable DuckDB analytics on AWS](../design/duckdb-scalable-analytics-architecture.md) from the supplied
discussion, with architecture, topology, query sequence, component, UML class, data model, data flow and worker
state diagrams. The document includes worker sizing, scheduling, Kubernetes examples, security boundaries,
operations, cost calculations, proposed decisions and acceptance experiments. README, the design index and
the changelog link to the proposal and distinguish it from implemented `sqlmem` features.

All capacity, latency, delivery and pricing inputs are labeled as planning assumptions. The design decisions
are proposed, not accepted repository ADRs. Current official DuckDB concurrency and Iceberg documentation were
consulted to distinguish embedded workers from Quack/DuckLake and a real Iceberg REST catalog.

## Verification

Documentation-only exception: `python scripts\verify.py` was **not run**. No package, tests, dependency manifests,
SQL execution code, retrieval behavior or requirement rows changed. No existing full-gate evidence is reused
as a claim about this change.

| Focused check | Outcome |
|---|---|
| Markdown structure | PASS: 15 numbered sections; balanced code fences |
| Kubernetes examples | PASS: two YAML documents parsed; selectors, resource values and HPA references checked |
| Baseline resource arithmetic | PASS: 32 worker nodes, 256 vCPU, 1,856 GiB |
| Cost arithmetic | PASS: baseline worker compute $11,859.40; other components $4,373-$9,073; peak worker compute $26,306.52 |
| Mermaid parsing and browser rendering | PASS: eight parsed diagrams and eight SVGs using the installed VS Code Mermaid bundle |
| Relative documentation links and whitespace | PASS: 74 relative links/anchors across seven documentation files; no trailing whitespace; `git diff --check` exit 0 |

### Reproduce structure, examples and arithmetic

From the repository root in PowerShell, using the existing environment's PyYAML:

```powershell
@'
from decimal import Decimal
from pathlib import Path
import re
import yaml
text = Path(r'docs\design\duckdb-scalable-analytics-architecture.md').read_text(encoding='utf-8')
assert text.count('```') % 2 == 0
assert re.findall(r'^## (\d+)\. ', text, re.M) == [str(n) for n in range(1, 16)]
blocks = re.findall(r'```yaml\n(.*?)```', text, re.S)
assert len(blocks) == 2
deployment, hpa = [yaml.safe_load(block) for block in blocks]
pod = deployment['spec']['template']['spec']
worker = pod['containers'][0]
assert deployment['kind'] == 'Deployment' and deployment['spec']['replicas'] == 18
assert deployment['spec']['selector']['matchLabels'].items() <= deployment['spec']['template']['metadata']['labels'].items()
assert worker['resources']['requests'] == {'cpu': '7', 'memory': '52Gi', 'ephemeral-storage': '180Gi'}
assert worker['resources']['limits'] == {'cpu': '8', 'memory': '54Gi', 'ephemeral-storage': '200Gi'}
assert pod['volumes'][0]['emptyDir']['sizeLimit'] == '180Gi'
env = {entry['name']: entry['value'] for entry in worker['env']}
assert (env['DUCKDB_MEMORY_LIMIT'], env['DUCKDB_MAX_TEMP_DIRECTORY_SIZE']) == ('42GB', '150GB')
assert env['DUCKDB_TEMP_DIRECTORY'] == worker['volumeMounts'][0]['mountPath']
assert hpa['spec']['scaleTargetRef']['name'] == deployment['metadata']['name']
assert hpa['metadata']['namespace'] == deployment['metadata']['namespace']
assert (hpa['spec']['minReplicas'], hpa['spec']['maxReplicas']) == (18, 36)
assert 18 * 8 + 10 * 8 + 4 * 8 == 256
assert 18 * 64 + 10 * 64 + 4 * 16 == 1856
baseline = 28 * Decimal('386.32') + 4 * Decimal('260.61')
peak = 60 * Decimal('386.32') + 12 * Decimal('260.61')
low = sum((2200, 500, 500, 500, 73, 200, 300, 100))
high = sum((2400, 1300, 1500, 1000, 73, 1000, 1000, 800))
for value in (baseline, peak, baseline + low, baseline + high):
    assert f'${value:,.2f}' in text, value
for value in (low, high):
    assert f'${value:,}' in text, value
print('Markdown structure: PASS (15 numbered sections, balanced fences)')
print('YAML examples: PASS (2 parsed; selectors, resources and HPA references checked)')
print('Capacity arithmetic: PASS (32 workers, 256 vCPU, 1,856 GiB)')
print(f'Cost arithmetic: PASS (baseline ${baseline:,.2f}; other ${low:,}-${high:,}; peak ${peak:,.2f})')
'@ | .\.venv\Scripts\python.exe -
```

Result: exit 0 with the four PASS lines above.

Negative evidence: the first arithmetic check raised `AssertionError: 20932.40`, exposing a draft upper
subtotal of $11,073 rather than $9,073. The final line items sum to $16,232.40-$20,932.40, rounded to a
$17,000-$21,000 planning allowance before omitted infrastructure and contingency.

### Reproduce Mermaid checks

The initial Node-only parser harness failed with `TypeError: wo.addHook is not a function` because its DOM stub
was insufficient for this bundle's sanitizer. No diagram defect was inferred from that environment failure.
The actual check used a real integrated browser and a temporary loopback-only server, without installing
packages or uploading document content.

The bundle path and minified bootstrap names below are specific to this VS Code build; replace `<user>` with your
Windows account. Start the helper in a PowerShell terminal from the repository root:

```powershell
@'
import { readFile } from 'node:fs/promises';
import http from 'node:http';
const { default: html } = await import('file:///C:/Users/<user>/AppData/Local/Programs/Microsoft%20VS%20Code/261c84cb1e/resources/app/extensions/markdown-language-features/markdown-editor-out/mermaid-5EJVVIDP.js');
const bundle = html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
if (!bundle.includes('szt().catch(ZFe);')) throw new Error('Unexpected Mermaid bootstrap');
const javascript = bundle.replace('szt().catch(ZFe);', 'globalThis.mermaid = ZK;');
const markdown = await readFile('docs\\design\\duckdb-scalable-analytics-architecture.md', 'utf8');
const diagrams = [...markdown.matchAll(/```mermaid\r?\n([\s\S]*?)```/g)].map(match => match[1]);
if (diagrams.length !== 8) throw new Error(`Expected 8 diagrams, got ${diagrams.length}`);
const runner = `globalThis.validation = { status: 'running', diagrams: [] };
(async () => {
  mermaid.initialize({startOnLoad:false});
  const diagrams = await (await fetch('/diagrams.json')).json();
  for (const [i, source] of diagrams.entries()) {
    await mermaid.parse(source);
    const {svg} = await mermaid.render('diagram-' + i, source);
    const section = document.createElement('section');
    section.innerHTML = '<h2>Diagram ' + (i+1) + '</h2>' + svg;
    document.body.appendChild(section);
    if (!section.querySelector('svg')) throw new Error('Missing SVG');
    validation.diagrams.push({index:i+1,type:source.split('\\n')[0],parsed:true,rendered:true});
  }
  validation.status = 'PASS';
  document.querySelector('#status').textContent = JSON.stringify(validation);
})().catch(error => {
  validation.status = 'FAIL'; validation.error = String(error);
  document.querySelector('#status').textContent = JSON.stringify(validation);
});`;
const server = http.createServer((req, res) => {
  const routes = {
    '/': ['text/html', '<!doctype html><html><head><title>DuckDB diagram validation</title></head><body><h1>DuckDB diagrams</h1><pre id="status">Running</pre><script src="/mermaid.js"></script><script src="/runner.js"></script></body></html>'],
    '/mermaid.js': ['text/javascript', javascript],
    '/runner.js': ['text/javascript', runner],
    '/diagrams.json': ['application/json', JSON.stringify(diagrams)]
  };
  const route = routes[req.url];
  if (!route) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, {'Content-Type': route[0]}); res.end(route[1]);
});
server.listen(18769, '127.0.0.1', () => console.log('READY http://127.0.0.1:18769'));
'@ | node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --input-type=module -
```

`Invoke-WebRequest -Uri 'http://127.0.0.1:18769/' -UseBasicParsing` returned HTTP 200. Open that URL locally
and inspect the status JSON. Browser evaluation through the integrated browser returned:

```text
status: PASS
diagrams: 8, each parsed: true and rendered: true
svgCount: 8
```

The diagrams were two architecture/topology flowcharts, one sequence diagram, one component flowchart,
one UML class diagram, one ER diagram, one data-flow diagram and one worker state diagram. The temporary
server was stopped after validation; stop a reproduced terminal helper with Ctrl+C when finished.

### Reproduce links and whitespace checks

```powershell
@'
from pathlib import Path
import re
files = [Path(r'README.md'), Path(r'CHANGELOG.md'), Path(r'docs\design\README.md'), Path(r'docs\design\duckdb-scalable-analytics-architecture.md'), Path(r'docs\evidence\2026-11-03-duckdb-architecture-documentation.md'), Path(r'docs\reviews\2026-11-03-duckdb-architecture-documentation.md'), Path(r'docs\status.md')]
checked = 0
fences = r'^```[^\n]*\n.*?^```\s*$'
for path in files:
    text = path.read_text(encoding='utf-8')
    for n, line in enumerate(text.splitlines(), 1):
        assert not line.endswith((' ', '\t')), f'{path}:{n}: trailing whitespace'
    text = re.sub(fences, '', text, flags=re.S | re.M)
    for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
        target = raw.strip().strip('<>')
        if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target):
            continue
        location, _, anchor = target.partition('#')
        resolved = (path.parent / location).resolve() if location else path.resolve()
        assert resolved.exists(), f'{path}: missing {target}'
        if anchor and resolved.suffix == '.md':
            anchors = set()
            counts = {}
            destination = re.sub(fences, '', resolved.read_text(encoding='utf-8'), flags=re.S | re.M)
            for heading in re.findall(r'^#{1,6}\s+(.+)', destination, re.M):
                slug = re.sub(r'[^\w -]', '', heading.lower()).replace(' ', '-')
                count = counts.get(slug, 0)
                anchors.add(slug if count == 0 else f'{slug}-{count}')
                counts[slug] = count + 1
            assert anchor in anchors, f'{path}: missing anchor {target}'
        checked += 1
print(f'Relative links and anchors: PASS ({checked} links across {len(files)} files)')
print(f'Whitespace: PASS ({len(files)} documentation files)')
'@ | .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git --no-pager diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Result: exit 0, `Relative links and anchors: PASS (74 links across 7 files)` and
`Whitespace: PASS (7 documentation files)`. The Python check includes newly created files regardless of
staging state; Git's whitespace check complements it for tracked edits.

## Review outcome

The independent reviewer approved the documentation-only change with no actionable correctness findings.
The [review record](../reviews/2026-11-03-duckdb-architecture-documentation.md) records that verdict, the
documentation-only gate exception and unverified deployment assumptions. The final relative-link and
whitespace checks include the review, evidence and handoff records.

## Gaps and risks

- Full Python gates, retrieval evaluation, requirement traceability and cross-engine runs were not rerun;
  only Markdown changed.
- YAML was parsed and its selected configuration relationships checked, not schema-validated by Kubernetes,
  server-side dry-run, scheduled or deployed.
- The container image, service interfaces, infrastructure code and isolation controls are proposals,
  not newly implemented software.
- No AWS resources were provisioned, no live prices obtained and no workload or failure benchmarks run.
- Pricing and SLOs remain unverified assumptions. The corrected totals prove arithmetic, not procurement cost.
- The browser check exercised Mermaid from the installed VS Code bundle, not every Markdown renderer.

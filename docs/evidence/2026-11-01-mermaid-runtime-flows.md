# Evidence: Mermaid runtime flow syntax

| | |
|---|---|
| Date | 2026-11-01 |
| Commit | Uncommitted working tree based on `fbddbded16b31ecd4c81fc44b18ced84c569c32e` |
| Requirements | No runtime behavior or requirement changes; documentation correction only |
| Review | [Review record](../reviews/2026-11-01-mermaid-runtime-flows.md) |
| CI run | Not run |

## Change

The scan sequence diagram in [runtime flows](../architecture/flows.md) contained a literal semicolon in a
message. Mermaid treated it as a statement separator and attempted to parse `sampled)` as another statement.
Replacing it with Mermaid's `#59;` entity preserves the displayed semicolon without splitting the message.
The changelog records the preview fix; no package code, dependencies or gates changed.

## Verification

Used the Mermaid bundle already shipped with the installed VS Code Markdown extension, without installing
dependencies or sending documentation to an external renderer.

| Check | Before | After |
|---|---|---|
| Parse diagram 1 | FAIL: `Parse error on line 17`, `got 'NEWLINE'` | PASS |
| Parse diagrams 2-6 | PASS | PASS |
| Browser rendering using the same bundle | Not run | All six diagrams produce SVG |
| Browser SVG text | Not run | Original `value dictionaries; sampled)` label preserved |
| `git diff --check` | Not run | PASS |

Reproduce the parser check from the repository root in PowerShell. Replace `<user>` with your Windows account;
the bundle path and minified startup names are specific to this VS Code build:

```powershell
@'
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
const { default: html } = await import('file:///C:/Users/<user>/AppData/Local/Programs/Microsoft%20VS%20Code/2c33b50b16/resources/app/extensions/markdown-language-features/markdown-editor-out/mermaid-5EJVVIDP.js');
const script = html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
globalThis.window = { addEventListener() {} };
globalThis.document = { querySelector: () => null };
vm.runInThisContext(script.replace('szt().catch(ZFe);', 'globalThis.mermaid = ZK;'));
mermaid.initialize({ startOnLoad: false });
const markdown = await readFile('docs\\architecture\\flows.md', 'utf8');
const diagrams = [...markdown.matchAll(/```mermaid\r?\n([\s\S]*?)```/g)];
if (diagrams.length !== 6) throw new Error(`Expected six diagrams, got ${diagrams.length}`);
for (const [i, match] of diagrams.entries()) {
  await mermaid.parse(match[1]);
  console.log(`Diagram ${i + 1}: PASS`);
}
'@ | node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --input-type=module -
```

Result: exit 0, `Diagram 1: PASS` through `Diagram 6: PASS`. Before the edit, the same bundle reproduced the
reported parser error in diagram 1, while diagrams 2-6 passed.

The browser check served the bundle and the six diagram sources on loopback only, then called `mermaid.parse`
and `mermaid.render` on each source. It asserted one SVG per diagram and the exact scan message text in the
first SVG. Result: `svgCount: 6`, every `parsed` and `rendered` flag `true`, `labelPreserved: true`.
The temporary server was stopped after verification.

## Review outcome

The independent reviewer reproduced the original failure and the successful parsing of all six edited diagrams,
and found no high-confidence defect in the fix. Its major finding requests fresh full Python gates. The author
accepted that omission under the documentation-only validation rule: package code is unchanged and the focused
checks exercise Mermaid itself. The [review record](../reviews/2026-11-01-mermaid-runtime-flows.md) preserves the
finding, reviewer verdict and author response; no full-suite pass or subsequent reviewer approval is claimed.

## Gaps and risks

- Full Python gates, retrieval evaluation and database engines were not rerun: only Markdown changed.
- Rendering was checked in the integrated browser using VS Code's bundled Mermaid, not by reopening the user's
  original Markdown preview.
- The parser reproduction command is tied to the installed VS Code bundle; after a VS Code update, use its
  current bundle path or check the diagrams in Markdown Preview.

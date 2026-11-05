import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_chart_vendor import EXPRESSIONS, TARGET, patch_gl


@pytest.mark.req("REQ-CHART-04", "REQ-CHART-07")
def test_gl_csp_patch_is_reproducible_and_closed():
    root = Path(__file__).parents[1] / "sqlmem" / "assets" / "vendor"
    patched = (root / "echarts-gl.min.js").read_bytes()
    marker, body = patched.decode("utf-8").split("\n", 1)
    assert "sqlmem CSP build" in marker
    start = body.index('function(width,height,dpr){switch(t[1].replace(/\\s+/g,"")){')
    end = body.index('default:throw new Error("Unsupported offline compositor expression.");}}', start)
    end += len('default:throw new Error("Unsupported offline compositor expression.");}}')
    original = (body[:start] + TARGET + body[end:]).encode("utf-8")
    assert patch_gl(original) == patched
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    gl = next(bundle for bundle in manifest["bundles"] if bundle["file"] == "echarts-gl.min.js")
    assert gl["upstream_sha256"] == hashlib.sha256(original).hexdigest()
    assert gl["sha256"] == hashlib.sha256(patched).hexdigest()
    assert len(EXPRESSIONS) == 22
    assert TARGET not in patched.decode("utf-8")
    assert all("width" in expression or "height" in expression for expression in EXPRESSIONS)
    with pytest.raises(ValueError, match="Unexpected upstream"):
        patch_gl(original + b"unexpected")

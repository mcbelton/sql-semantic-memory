"""Reproduce the narrow CSP-only patch for the pinned upstream ECharts GL bundle."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

UPSTREAM_SHA256 = "d6d60f2165ce3eb1ea360ef62e8490835e0ae2c1e0c1788a772fff918e350842"
TARGET = 'new Function("width","height","dpr","return "+t[1])'
EXPRESSIONS = (
    "width*1.0",
    "height*1.0",
    *(f"{dimension}*1.0/{divisor}" for dimension in ("width", "height") for divisor in (2, 4, 8, 16, 32)),
    "[width*1.0,height*1.0]",
    *(f"[width*1.0/{divisor},height*1.0/{divisor}]" for divisor in (2, 4, 8, 16)),
    *(f"[width*1.0/{divisor},height/{divisor}]" for divisor in (2, 4, 8, 16, 32)),
)


def patch_gl(source: bytes) -> bytes:
    if hashlib.sha256(source).hexdigest() != UPSTREAM_SHA256:
        raise ValueError("Unexpected upstream ECharts GL bytes; review the new release before changing the pin.")
    text = source.decode("utf-8")
    actual = {re.sub(r"\s+", "", expression) for expression in re.findall(r"expr\(([^)]*)\)", text)}
    if actual != set(EXPRESSIONS) or text.count(TARGET) != 1:
        raise ValueError("Upstream compositor changed; review its expression inventory before rebuilding.")
    cases = "".join(f'case"{expression}":return {expression};' for expression in EXPRESSIONS)
    replacement = (
        'function(width,height,dpr){switch(t[1].replace(/\\s+/g,"")){'
        + cases
        + 'default:throw new Error("Unsupported offline compositor expression.");}}'
    )
    notice = (
        "/* sqlmem CSP build: the fixed upstream compositor expressions use an exhaustive static switch, "
        "not dynamic JavaScript compilation. See scripts/build_chart_vendor.py and manifest.json. */\n"
    )
    return (notice + text.replace(TARGET, replacement)).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    patched = patch_gl(args.upstream.read_bytes())
    args.output.write_bytes(patched)
    print(f"sha256={hashlib.sha256(patched).hexdigest()} bytes={len(patched)}")


if __name__ == "__main__":
    main()

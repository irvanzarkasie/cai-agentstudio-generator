#!/usr/bin/env python3
"""Smoke-test Phase 1 hybrid RAG tools locally."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_ROOT = (
    REPO_ROOT / "studio-data/workflows/hybrid_rag_agentic/tools"
)


def run_tool(tool_name: str, tool_params: dict) -> str:
    tool_py = TOOLS_ROOT / tool_name / "tool.py"
    cmd = [
        sys.executable,
        str(tool_py),
        "--user-params",
        "{}",
        "--tool-params",
        json.dumps(tool_params),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    line = result.stdout.strip().splitlines()[-1]
    prefix = "tool_output "
    if not line.startswith(prefix):
        raise RuntimeError(f"Unexpected output: {line}")
    return line[len(prefix) :]


def main() -> int:
    if not TOOLS_ROOT.is_dir():
        print("Run scripts/bundle_hybrid_data.py first", file=sys.stderr)
        return 1

    search = json.loads(run_tool("search_design_patterns", {"query": "enterprise RAG", "limit": 3}))
    print(f"search_design_patterns: {len(search)} patterns")
    if not search:
        print("FAIL: expected search hits", file=sys.stderr)
        return 1

    pn = search[0]["pattern_number"]
    detail = json.loads(run_tool("retrieve_pattern_technical_context", {"pattern_number": pn}))
    print(f"retrieve_pattern_technical_context: pattern {pn}, slice={detail.get('slice')}")
    if not detail.get("technical_text"):
        print("FAIL: expected technical_text", file=sys.stderr)
        return 1

    print("Phase 1 tool smoke test OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

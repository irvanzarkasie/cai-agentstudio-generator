#!/usr/bin/env python3
"""Smoke-test hybrid RAG tools locally and under Agent Studio sandbox env simulation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_ROOT = REPO_ROOT / "studio-data/workflows/hybrid_rag_agentic/tools"

QUERY = "enterprise RAG with reranking and citations"


def run_tool(tool_name: str, tool_params: dict, *, cwd: Path | None = None, env: dict | None = None) -> str:
    tool_py = TOOLS_ROOT / tool_name / "tool.py"
    cmd = [
        sys.executable,
        str(tool_py),
        "--user-params",
        "{}",
        "--tool-params",
        json.dumps(tool_params),
    ]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd or REPO_ROOT),
        env=merged_env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{tool_name} exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
        )
    line = result.stdout.strip().splitlines()[-1]
    prefix = "tool_output "
    if not line.startswith(prefix):
        raise RuntimeError(f"Unexpected output from {tool_name}: {line}")
    return line[len(prefix) :]


def assert_no_stub(tool_name: str, output: str) -> None:
    if "STUB [" in output:
        raise RuntimeError(f"{tool_name} still returns stub output")
    parsed = json.loads(output)
    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"{tool_name} returned error JSON: {parsed}")


def test_isolated_tool_dir(tool_name: str, tool_params: dict) -> None:
    """Reproduce Agent Studio sandbox: only tool directory contents, no parent lib/."""
    import shutil
    import tempfile

    tool_src = TOOLS_ROOT / tool_name
    with tempfile.TemporaryDirectory() as tmp:
        isolated = Path(tmp) / tool_name
        shutil.copytree(tool_src, isolated)
        cmd = [
            sys.executable,
            str(isolated / "tool.py"),
            "--user-params",
            "{}",
            "--tool-params",
            json.dumps(tool_params),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
            env={**os.environ, "WORKFLOW_DATA_DIRECTORY": "/workflow_data"},
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"isolated {tool_name} exited {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        line = result.stdout.strip().splitlines()[-1]
        prefix = "tool_output "
        if not line.startswith(prefix):
            raise RuntimeError(f"Unexpected isolated output from {tool_name}: {line}")
        assert_no_stub(tool_name, line[len(prefix) :])


def test_sandbox_simulation() -> None:
    """Simulate Agent Studio: cwd=artifact root + WORKFLOW_DATA_DIRECTORY=/workflow_data."""
    fake_workflow_data = "/workflow_data"
    env = {"WORKFLOW_DATA_DIRECTORY": fake_workflow_data}
    search = json.loads(
        run_tool(
            "search_design_patterns",
            {"query": QUERY, "limit": 2},
            cwd=REPO_ROOT,
            env=env,
        )
    )
    assert_no_stub("search_design_patterns", json.dumps(search))
    if not search:
        raise RuntimeError("sandbox simulation: expected search hits")
    print(f"sandbox simulation: search_design_patterns returned {len(search)} patterns with WORKFLOW_DATA_DIRECTORY set")

    test_isolated_tool_dir("search_design_patterns", {"query": QUERY, "limit": 2})
    test_isolated_tool_dir("recommend_hybrid_agentic_workflow", {"query": QUERY})
    print("isolated tool dir tests OK (lib vendored per tool)")


def main() -> int:
    if not TOOLS_ROOT.is_dir():
        print("Run scripts/bundle_hybrid_data.py first", file=sys.stderr)
        return 1

    test_sandbox_simulation()

    search = json.loads(run_tool("search_design_patterns", {"query": QUERY, "limit": 3}))
    assert_no_stub("search_design_patterns", json.dumps(search))
    print(f"search_design_patterns: {len(search)} patterns")
    if not search:
        print("FAIL: expected search hits", file=sys.stderr)
        return 1

    pn = search[0]["pattern_number"]

    detail = json.loads(run_tool("retrieve_pattern_technical_context", {"pattern_number": pn}))
    assert_no_stub("retrieve_pattern_technical_context", json.dumps(detail))
    print(f"retrieve_pattern_technical_context: pattern {pn}, slice={detail.get('slice')}")
    if not detail.get("technical_text"):
        print("FAIL: expected technical_text", file=sys.stderr)
        return 1

    pattern = json.loads(run_tool("get_design_pattern", {"pattern_number": pn}))
    assert_no_stub("get_design_pattern", json.dumps(pattern))
    print(f"get_design_pattern: {pattern.get('name')}")

    concepts = json.loads(run_tool("patterns_using_concept", {"concept_name": "rag"}))
    assert_no_stub("patterns_using_concept", json.dumps(concepts))
    print(f"patterns_using_concept: {len(concepts)} patterns for 'rag'")

    related = json.loads(run_tool("related_design_patterns", {"pattern_number": pn, "limit": 3}))
    assert_no_stub("related_design_patterns", json.dumps(related))
    print(f"related_design_patterns: {len(related)} related")

    neighborhood = json.loads(run_tool("traverse_pattern_neighborhood", {"pattern_number": pn, "max_depth": 2}))
    assert_no_stub("traverse_pattern_neighborhood", json.dumps(neighborhood))
    print(f"traverse_pattern_neighborhood: {len(neighborhood.get('layers', []))} layers")

    stack = json.loads(run_tool("recommend_hybrid_agentic_workflow", {"query": QUERY}))
    assert_no_stub("recommend_hybrid_agentic_workflow", json.dumps(stack))
    print(f"recommend_hybrid_agentic_workflow: {len(stack.get('recommended_stack', []))} stack steps")

    expanded = json.loads(run_tool("expand_design_patterns", {"query": QUERY}))
    assert_no_stub("expand_design_patterns", json.dumps(expanded))
    print(
        "expand_design_patterns:",
        f"{len(expanded.get('primary_patterns', []))} primary,",
        f"{len(expanded.get('expanded_patterns', []))} expanded",
    )

    bundle = json.loads(run_tool("build_hybrid_context_bundle", {"query": QUERY}))
    assert_no_stub("build_hybrid_context_bundle", json.dumps(bundle))
    print(
        "build_hybrid_context_bundle:",
        f"{len(bundle.get('evidence', []))} evidence sections,",
        f"{len(bundle.get('expanded_technical', []))} expanded technical",
    )

    validation = json.loads(run_tool("validate_hybrid_retrieval", {"query": QUERY}))
    assert_no_stub("validate_hybrid_retrieval", json.dumps(validation))
    print(f"validate_hybrid_retrieval: passed={validation.get('passed')}")

    reflection = json.loads(run_tool("reflect_on_hybrid_retrieval", {"query": QUERY}))
    assert_no_stub("reflect_on_hybrid_retrieval", json.dumps(reflection))
    print(f"reflect_on_hybrid_retrieval: action={reflection.get('action')}")

    print("All 11 hybrid RAG tool smoke tests OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

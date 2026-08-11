#!/usr/bin/env python3
"""
Verify Phase 1 hybrid RAG artifact readiness for GitHub deploy.

Checks structure, local tool smoke tests, packaging layout, and repo-root constraint.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = REPO_ROOT
WORKFLOW_NAME = "Hybrid RAG Agentic Workflow"

PHASE1_TOOLS = frozenset({"search_design_patterns", "retrieve_pattern_technical_context"})


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def main() -> int:
    results: list[bool] = []

    # --- artifact paths ---
    results.append(check("Artifact directory exists", ARTIFACT_ROOT.is_dir(), str(ARTIFACT_ROOT)))

    for name in ("workflow.yaml", "collated_input.json"):
        p = ARTIFACT_ROOT / name
        results.append(check(f"Root file: {name}", p.is_file()))

    studio = ARTIFACT_ROOT / "studio-data"
    results.append(check("studio-data/ present", studio.is_dir()))

    data_graph = ARTIFACT_ROOT / "studio-data/workflows/hybrid_rag_agentic/data/graph.json"
    slices = ARTIFACT_ROOT / "studio-data/workflows/hybrid_rag_agentic/data/slices"
    results.append(check("Bundled graph.json", data_graph.is_file(), f"{data_graph.stat().st_size // 1024} KB"))
    slice_count = len(list(slices.glob("pages_*.md"))) if slices.is_dir() else 0
    results.append(check("Bundled book slices", slice_count >= 10, f"{slice_count} markdown files"))

    # --- collated_input sanity ---
    collated = json.loads((ARTIFACT_ROOT / "collated_input.json").read_text(encoding="utf-8"))
    wf_name = collated.get("workflow", {}).get("name", "")
    results.append(check("Workflow name", wf_name == WORKFLOW_NAME, wf_name))

    agents = collated.get("agents", [])
    tasks = collated.get("tasks", [])
    tools = collated.get("tool_instances", [])
    results.append(check("Agent count", len(agents) == 3, str(len(agents))))
    results.append(check("Task count", len(tasks) == 3, str(len(tasks))))
    results.append(check("Tool instance count", len(tools) == 11, str(len(tools))))

    stub_tools = []
    for tool in tools:
        folder = ARTIFACT_ROOT / tool["source_folder_path"]
        code = (folder / "tool.py").read_text(encoding="utf-8")
        slug = folder.name
        if "STUB [" in code:
            stub_tools.append(slug)

    implemented = sorted(PHASE1_TOOLS - set(stub_tools))
    results.append(
        check(
            "Phase 1 tools implemented",
            len(implemented) == len(PHASE1_TOOLS),
            ", ".join(implemented) or "none",
        )
    )
    results.append(
        check(
            "Stub tools (expected for Phase 1)",
            len(stub_tools) == 9,
            f"{len(stub_tools)} stubs — OK for deploy, limited at runtime",
        )
    )

    # --- validate.py ---
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/validate.py"), "--root", str(ARTIFACT_ROOT)],
        capture_output=True,
        text=True,
    )
    results.append(check("validate.py", proc.returncode == 0, proc.stdout.strip() or proc.stderr.strip()))

    # --- tool smoke test ---
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/test_hybrid_tools.py")],
        capture_output=True,
        text=True,
    )
    results.append(check("test_hybrid_tools.py", proc.returncode == 0, proc.stdout.strip().splitlines()[-1] if proc.stdout else proc.stderr.strip()))

    # --- packaging layout (what Agent Studio expects at clone root) ---
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = Path(tmp) / "artifact.tar.gz"
        staging = Path(tmp) / "staging"
        staging.mkdir()
        for name in ("workflow.yaml", "collated_input.json"):
            shutil_copy = __import__("shutil")
            shutil_copy.copy2(ARTIFACT_ROOT / name, staging / name)
        shutil_copy.copytree(ARTIFACT_ROOT / "studio-data", staging / "studio-data")
        with tarfile.open(tar_path, "w:gz") as tar:
            for path in staging.rglob("*"):
                if path.is_file():
                    tar.add(path, arcname=path.relative_to(staging).as_posix())
        names = tarfile.open(tar_path).getnames()
        results.append(check("Package contains workflow.yaml", "workflow.yaml" in names))
        results.append(check("Package contains collated_input.json", "collated_input.json" in names))
        results.append(
            check(
                "Package contains graph data",
                any("data/graph.json" in n for n in names),
            )
        )

    results.append(
        check(
            "GitHub deploy layout",
            (REPO_ROOT / "workflow.yaml").is_file() and (REPO_ROOT / "collated_input.json").is_file(),
            "workflow.yaml + collated_input.json at repository root (Agent Studio GitHub target)",
        )
    )
    print()
    print("Runtime expectation (Phase 1):")
    print("  - Deploy + kickoff should succeed")
    print("  - search_design_patterns + retrieve_pattern_technical_context return real data")
    print("  - Other 9 tools return STUB responses — agents may behave oddly until Phase 2")

    gate = results
    ok = all(gate)
    print()
    print("Deploy path:")
    print("  git push origin main")
    print("  python scripts/deploy.py --config deploy/deployment-config.example.json --wait 180 --insecure")
    print(f"  Local checks: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

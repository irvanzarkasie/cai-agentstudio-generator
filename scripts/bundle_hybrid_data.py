#!/usr/bin/env python3
"""Bundle hybrid RAG lib + corpus data into crew_hybrid_agentic artifact (Phase 1)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path("/Users/izarkasie/Documents/sourcecodes/docling-conv-docs/generative_ai_design_patterns")
DEFAULT_ARTIFACT = REPO_ROOT / "examples" / "crew_hybrid_agentic"
WORKFLOW_REL = Path("studio-data/workflows/hybrid_rag_agentic")

SEARCH_TOOL = '''\
"""Search design patterns in the knowledge graph."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

_TOOL_FILE = Path(__file__)
sys.path.insert(0, str(_TOOL_FILE.resolve().parent.parent.parent / "lib"))
from tool_runtime import HybridUserParameters, build_toolkit


class UserParameters(HybridUserParameters):
    pass


class ToolParameters(BaseModel):
    query: str = Field(description="User question to match against design patterns")
    limit: int = Field(default=5, description="Maximum number of patterns to return")


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    toolkit = build_toolkit(config, _TOOL_FILE)
    return toolkit.search_design_patterns(args.query, limit=args.limit)


OUTPUT_KEY = "tool_output"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True)
    parser.add_argument("--tool-params", required=True)
    cli = parser.parse_args()
    config = UserParameters(**json.loads(cli.user_params))
    params = ToolParameters(**json.loads(cli.tool_params))
    print(OUTPUT_KEY, run_tool(config, params))
'''

RETRIEVE_TOOL = '''\
"""Retrieve book-grounded technical context for one design pattern."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

_TOOL_FILE = Path(__file__)
sys.path.insert(0, str(_TOOL_FILE.resolve().parent.parent.parent / "lib"))
from tool_runtime import HybridUserParameters, build_toolkit


class UserParameters(HybridUserParameters):
    pass


class ToolParameters(BaseModel):
    pattern_number: int = Field(description="Design pattern number (1-32)")


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    toolkit = build_toolkit(config, _TOOL_FILE)
    return toolkit.retrieve_pattern_technical_context(args.pattern_number)


OUTPUT_KEY = "tool_output"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True)
    parser.add_argument("--tool-params", required=True)
    cli = parser.parse_args()
    config = UserParameters(**json.loads(cli.user_params))
    params = ToolParameters(**json.loads(cli.tool_params))
    print(OUTPUT_KEY, run_tool(config, params))
'''

TOOL_REQUIREMENTS = "pydantic>=2.0.0\n"


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle hybrid RAG Phase 1 assets")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()

    source = args.source.resolve()
    artifact = args.artifact.resolve()
    workflow_root = artifact / WORKFLOW_REL

    graph_src = source / "outputs" / "merged" / "graph.json"
    slices_src = source / "slices" / "by_50"
    lib_src = REPO_ROOT / "converters" / "hybrid_rag_lib"

    for path, label in (
        (graph_src, "graph.json"),
        (slices_src, "slices/by_50"),
        (lib_src, "hybrid_rag_lib"),
        (workflow_root, "artifact workflow root"),
    ):
        if not path.exists():
            print(f"Missing {label}: {path}", file=sys.stderr)
            return 1

    data_dir = workflow_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(graph_src, data_dir / "graph.json")
    copy_tree(slices_src, data_dir / "slices")
    copy_tree(lib_src, workflow_root / "lib")

    phase1_tools = {
        "search_design_patterns": SEARCH_TOOL,
        "retrieve_pattern_technical_context": RETRIEVE_TOOL,
    }
    for tool_name, tool_py in phase1_tools.items():
        tool_dir = workflow_root / "tools" / tool_name
        tool_dir.mkdir(parents=True, exist_ok=True)
        (tool_dir / "tool.py").write_text(tool_py, encoding="utf-8")
        (tool_dir / "requirements.txt").write_text(TOOL_REQUIREMENTS, encoding="utf-8")

    print(f"Bundled Phase 1 assets into {artifact}")
    print(f"  graph: {data_dir / 'graph.json'}")
    print(f"  slices: {len(list((data_dir / 'slices').glob('pages_*.md')))} markdown files")
    print(f"  lib: {workflow_root / 'lib'}")
    print(f"  tools: {', '.join(phase1_tools)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

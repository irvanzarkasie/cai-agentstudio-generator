#!/usr/bin/env python3
"""Bundle hybrid RAG lib + corpus data + tool entrypoints into the workflow artifact."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACT = REPO_ROOT


def resolve_source(source: Path | None) -> Path | None:
    """Return corpus source directory, or None to keep existing bundled data."""
    if source is not None:
        return source.resolve()
    env = os.environ.get("HYBRID_RAG_SOURCE", "").strip()
    if env:
        return Path(env).resolve()
    return None
WORKFLOW_REL = Path("studio-data/workflows/hybrid_rag_agentic")

TOOL_REQUIREMENTS = "pydantic>=2.0.0\n"

# (field_name, type, description, default or None)
ToolParam = tuple[str, str, str, str | None]

TOOL_SPECS: dict[str, tuple[str, list[ToolParam], str]] = {
    "search_design_patterns": (
        "Search design patterns in the knowledge graph.",
        [
            ("query", "str", "User question to match against design patterns", None),
            ("limit", "int", "Maximum number of patterns to return", "5"),
        ],
        "toolkit.search_design_patterns(args.query, limit=args.limit)",
    ),
    "get_design_pattern": (
        "Fetch full graph metadata for one design pattern by its pattern number (1-32).",
        [
            ("pattern_number", "int", "Design pattern number (1-32)", None),
        ],
        "toolkit.get_design_pattern(args.pattern_number)",
    ),
    "patterns_using_concept": (
        "List design patterns linked to a concept in the graph (e.g. RAG, reflection).",
        [
            ("concept_name", "str", "Concept name to look up in the knowledge graph", None),
        ],
        "toolkit.patterns_using_concept(args.concept_name)",
    ),
    "related_design_patterns": (
        "Find graph-related patterns via related_patterns links and shared concepts.",
        [
            ("pattern_number", "int", "Anchor design pattern number (1-32)", None),
            ("limit", "int", "Maximum number of related patterns to return", "5"),
        ],
        "toolkit.related_design_patterns(args.pattern_number, limit=args.limit)",
    ),
    "traverse_pattern_neighborhood": (
        "Traverse the pattern knowledge graph neighborhood (Index-Aware / graph-augmented retrieval).",
        [
            ("pattern_number", "int", "Starting design pattern number (1-32)", None),
            ("max_depth", "int", "Maximum graph traversal depth (1-3)", "2"),
        ],
        "toolkit.traverse_pattern_neighborhood(args.pattern_number, max_depth=args.max_depth)",
    ),
    "recommend_hybrid_agentic_workflow": (
        "Return the canonical hybrid KG + text agentic workflow pattern stack from the book.",
        [
            ("query", "str", "User question used to contextualize the recommended stack", None),
        ],
        "toolkit.recommend_hybrid_agentic_workflow(args.query)",
    ),
    "expand_design_patterns": (
        "Expand context with supplementary patterns (safety, production, excerpt refs, graph links).",
        [
            ("query", "str", "User question driving pattern expansion", None),
        ],
        "toolkit.expand_design_patterns(args.query)",
    ),
    "retrieve_pattern_technical_context": (
        "Retrieve book technical sections and code examples for a pattern from slice markdown.",
        [
            ("pattern_number", "int", "Design pattern number (1-32)", None),
        ],
        "toolkit.retrieve_pattern_technical_context(args.pattern_number)",
    ),
    "build_hybrid_context_bundle": (
        "Run the full deterministic hybrid pipeline (graph + book slices) and return JSON context.",
        [
            ("query", "str", "User question to build the hybrid retrieval bundle for", None),
        ],
        "toolkit.build_hybrid_context_json(args.query)",
    ),
    "validate_hybrid_retrieval": (
        "Validate whether current hybrid retrieval has sufficient graph + book coverage.",
        [
            ("query", "str", "User question to validate hybrid retrieval for", None),
        ],
        "toolkit.validate_hybrid_retrieval(args.query)",
    ),
    "reflect_on_hybrid_retrieval": (
        "Self-RAG-style reflection: decide if retrieval is sufficient or needs expansion.",
        [
            ("query", "str", "User question to reflect on hybrid retrieval for", None),
        ],
        "toolkit.reflect_on_hybrid_retrieval(args.query)",
    ),
}


def render_tool_py(docstring: str, params: list[ToolParam], call_expr: str) -> str:
    param_lines: list[str] = []
    for name, typ, description, default in params:
        if default is None:
            param_lines.append(
                f'    {name}: {typ} = Field(description="{description}")'
            )
        else:
            param_lines.append(
                f'    {name}: {typ} = Field(default={default}, description="{description}")'
            )
    params_block = "\n".join(param_lines)

    return f'''\
"""{docstring}"""

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
{params_block}


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    toolkit = build_toolkit(config, _TOOL_FILE)
    return {call_expr}


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


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle hybrid RAG assets and tool entrypoints")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Upstream corpus root (must contain outputs/merged/graph.json and slices/by_50/). "
        "Optional: set HYBRID_RAG_SOURCE env var. Omit to refresh lib/tools only.",
    )
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()

    source = resolve_source(args.source)
    artifact = args.artifact.resolve()
    workflow_root = artifact / WORKFLOW_REL
    lib_src = REPO_ROOT / "converters" / "hybrid_rag_lib"

    if not lib_src.is_dir():
        print(f"Missing hybrid_rag_lib: {lib_src}", file=sys.stderr)
        return 1
    if not workflow_root.is_dir():
        print(f"Missing artifact workflow root: {workflow_root}", file=sys.stderr)
        return 1

    data_dir = workflow_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if source is not None:
        graph_src = source / "outputs" / "merged" / "graph.json"
        slices_src = source / "slices" / "by_50"
        for path, label in (
            (graph_src, "graph.json"),
            (slices_src, "slices/by_50"),
        ):
            if not path.exists():
                print(f"Missing {label}: {path}", file=sys.stderr)
                return 1
        shutil.copy2(graph_src, data_dir / "graph.json")
        copy_tree(slices_src, data_dir / "slices")
        print(f"  refreshed corpus from {source}")
    else:
        if not (data_dir / "graph.json").is_file():
            print(
                "No bundled graph.json found. Pass --source or set HYBRID_RAG_SOURCE.",
                file=sys.stderr,
            )
            return 1
        print("  kept existing bundled corpus (pass --source to refresh graph + slices)")

    copy_tree(lib_src, workflow_root / "lib")

    for tool_name, (docstring, params, call_expr) in TOOL_SPECS.items():
        tool_dir = workflow_root / "tools" / tool_name
        tool_dir.mkdir(parents=True, exist_ok=True)
        (tool_dir / "tool.py").write_text(
            render_tool_py(docstring, params, call_expr),
            encoding="utf-8",
        )
        (tool_dir / "requirements.txt").write_text(TOOL_REQUIREMENTS, encoding="utf-8")

    print(f"Bundled hybrid RAG assets into {artifact}")
    print(f"  graph: {data_dir / 'graph.json'}")
    print(f"  slices: {len(list((data_dir / 'slices').glob('pages_*.md')))} markdown files")
    print(f"  lib: {workflow_root / 'lib'}")
    print(f"  tools: {len(TOOL_SPECS)} ({', '.join(TOOL_SPECS)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

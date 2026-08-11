"""Shared helpers for Agent Studio hybrid RAG tool entrypoints."""

from __future__ import annotations

import sys
import os
from pathlib import Path

from pydantic import BaseModel, Field

from hybrid_rag import HybridRAGToolkit
from paths import resolve_data_path, workflow_data_root


class HybridUserParameters(BaseModel):
    graph_path: str = Field(
        default="data/graph.json",
        description="Path to knowledge graph JSON, relative to workflow data root",
    )
    slices_dir: str = Field(
        default="data/slices",
        description="Directory of book slice markdown files",
    )


def workflow_lib_dir(tool_file: Path) -> Path:
    return tool_file.resolve().parent.parent.parent / "lib"


def ensure_lib_on_path(tool_file: Path) -> None:
    lib = workflow_lib_dir(tool_file)
    lib_str = str(lib)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)


def build_toolkit(config: HybridUserParameters, tool_file: Path) -> HybridRAGToolkit:
    graph_path = resolve_data_path(config.graph_path, tool_file=tool_file)
    slices_dir = resolve_data_path(config.slices_dir, tool_file=tool_file)
    if not graph_path.is_file():
        raise FileNotFoundError(
            f"Graph not found: {graph_path}. "
            f"Bundled corpus expected at {workflow_data_root(tool_file=tool_file) / 'data'}. "
            f"WORKFLOW_DATA_DIRECTORY={os.environ.get('WORKFLOW_DATA_DIRECTORY', '(unset)')}"
        )
    if not slices_dir.is_dir():
        raise FileNotFoundError(
            f"Slices directory not found: {slices_dir}. "
            f"WORKFLOW_DATA_DIRECTORY={os.environ.get('WORKFLOW_DATA_DIRECTORY', '(unset)')}"
        )
    return HybridRAGToolkit(graph_path, slices_dir)

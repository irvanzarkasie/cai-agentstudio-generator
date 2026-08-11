"""Resolve workflow data paths for Agent Studio tool sandboxes."""

from __future__ import annotations

import os
from pathlib import Path


def workflow_data_root(*, tool_file: Path | None = None) -> Path:
    """Root directory containing data/ and lib/ for hybrid_rag_agentic."""
    env = os.environ.get("WORKFLOW_DATA_DIRECTORY")
    if env:
        return Path(env)
    if tool_file is None:
        return Path(__file__).resolve().parent.parent
    # .../hybrid_rag_agentic/tools/<name>/tool.py -> hybrid_rag_agentic
    return tool_file.resolve().parent.parent.parent


def resolve_data_path(relative: str, *, tool_file: Path) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return workflow_data_root(tool_file=tool_file) / path

"""Resolve workflow data paths for Agent Studio tool sandboxes."""

from __future__ import annotations

import os
from pathlib import Path

WORKFLOW_SLUG = "hybrid_rag_agentic"
BUNDLED_DATA_PREFIX = Path("studio-data/workflows") / WORKFLOW_SLUG


def workflow_data_root(*, tool_file: Path | None = None) -> Path:
    """
    Root directory containing data/ and lib/ for hybrid_rag_agentic.

    Agent Studio venv tools run with ``cwd=workflow_directory`` (artifact root)
    but also set ``WORKFLOW_DATA_DIRECTORY=/workflow_data`` for read-only project
    files. That env var must *not* be treated as the bundled corpus root — graph
    and slices live next to tools under ``studio-data/workflows/hybrid_rag_agentic/``.
    """
    if tool_file is not None:
        return tool_file.resolve().parent.parent.parent
    return Path(__file__).resolve().parent.parent


def _candidate_paths(relative: Path, *, tool_file: Path) -> list[Path]:
    candidates: list[Path] = []

    def add(path: Path) -> None:
        if path not in candidates:
            candidates.append(path)

    cwd = Path.cwd()
    tool_dir = tool_file.resolve().parent
    # Vendored corpus copied into each tool directory for /tool sandbox isolation.
    add(tool_dir / relative)
    # cwd is workflow_directory (artifact root) in Agent Studio when available.
    add(cwd / BUNDLED_DATA_PREFIX / relative)
    add(cwd / relative)
    add(workflow_data_root(tool_file=tool_file) / relative)

    workflow_data = os.environ.get("WORKFLOW_DATA_DIRECTORY", "").strip()
    if workflow_data:
        wf = Path(workflow_data)
        add(wf / BUNDLED_DATA_PREFIX / relative)
        add(wf / relative)

    return candidates


def resolve_data_path(relative: str, *, tool_file: Path) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path

    for candidate in _candidate_paths(path, tool_file=tool_file):
        if candidate.exists():
            return candidate

    return _candidate_paths(path, tool_file=tool_file)[0]

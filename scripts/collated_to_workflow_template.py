#!/usr/bin/env python3
"""
Build an Agent Studio workflow template ZIP from collated_input.json.

Agent Studio UI templates use workflow_template.json plus studio-data/tool_templates/
folders — not the GitHub CollatedInput layout. Generated zips can be imported via
Workflows → Templates → Import Template (see scripts/import_workflow_template.py).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_VERSION = "0.0.1"
DEFAULT_COLLATED = REPO_ROOT / "collated_input.json"
DEFAULT_OUT = REPO_ROOT / "dist" / "hybrid_rag_agentic_workflow_template.zip"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return slug or "tool"


def new_id() -> str:
    return str(uuid4())


def task_name(task: dict[str, Any], index: int) -> str:
    desc = (task.get("description") or "").strip().splitlines()[0]
    desc = re.sub(r"^Analyze the user query:\s*", "", desc, flags=re.IGNORECASE)
    desc = desc.strip('" ')
    if len(desc) > 60:
        desc = desc[:57].rstrip() + "..."
    return desc or f"Task {index + 1}"


def build_template(collated: dict[str, Any], artifact_root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    workflow_template_id = new_id()

    tool_id_map: dict[str, str] = {}
    tool_templates: list[dict[str, Any]] = []
    tool_dirs: dict[str, Path] = {}

    for tool in collated.get("tool_instances", []):
        old_id = tool["id"]
        tool_template_id = new_id()
        tool_id_map[old_id] = tool_template_id

        source_rel = Path(tool["source_folder_path"])
        slug = source_rel.name or slugify(tool.get("name", "tool"))
        template_folder = Path("studio-data") / "tool_templates" / slug
        source_dir = artifact_root / source_rel
        if not source_dir.is_dir():
            raise FileNotFoundError(f"Tool source directory not found: {source_dir}")

        tool_templates.append(
            {
                "id": tool_template_id,
                "workflow_template_id": workflow_template_id,
                "name": tool.get("name", slug),
                "python_code_file_name": tool.get("python_code_file_name", "tool.py"),
                "python_requirements_file_name": tool.get(
                    "python_requirements_file_name", "requirements.txt"
                ),
                "source_folder_path": template_folder.as_posix(),
                "pre_built": False,
                "tool_image_path": "",
                "is_venv_tool": bool(tool.get("is_venv_tool", True)),
            }
        )
        tool_dirs[template_folder.as_posix()] = source_dir

    agent_id_map: dict[str, str] = {}
    agent_templates: list[dict[str, Any]] = []
    for agent in collated.get("agents", []):
        old_id = agent["id"]
        agent_template_id = new_id()
        agent_id_map[old_id] = agent_template_id
        agent_templates.append(
            {
                "id": agent_template_id,
                "workflow_template_id": workflow_template_id,
                "name": agent.get("name", "Agent"),
                "description": "",
                "role": agent.get("crew_ai_role", ""),
                "backstory": agent.get("crew_ai_backstory", ""),
                "goal": agent.get("crew_ai_goal", ""),
                "allow_delegation": bool(agent.get("crew_ai_allow_delegation", False)),
                "verbose": bool(agent.get("crew_ai_verbose", True)),
                "cache": bool(agent.get("crew_ai_cache", True)),
                "temperature": float(agent.get("crew_ai_temperature", 0.2)),
                "max_iter": int(agent.get("crew_ai_max_iter", 15)),
                "tool_template_ids": [
                    tool_id_map[tid]
                    for tid in agent.get("tool_instance_ids", [])
                    if tid in tool_id_map
                ],
                "pre_packaged": False,
                "agent_image_path": "",
            }
        )

    task_templates: list[dict[str, Any]] = []
    task_template_ids: list[str] = []
    wf = collated["workflow"]
    task_by_id = {t["id"]: t for t in collated.get("tasks", [])}
    for index, task_id in enumerate(wf.get("task_ids", [])):
        task = task_by_id[task_id]
        task_template_id = new_id()
        task_template_ids.append(task_template_id)
        assigned = task.get("assigned_agent_id")
        task_templates.append(
            {
                "id": task_template_id,
                "workflow_template_id": workflow_template_id,
                "name": task_name(task, index),
                "description": task.get("description", ""),
                "expected_output": task.get("expected_output", ""),
                "assigned_agent_template_id": agent_id_map.get(assigned, ""),
            }
        )

    agent_template_ids = [agent_id_map[aid] for aid in wf.get("agent_ids", []) if aid in agent_id_map]

    payload = {
        "template_version": TEMPLATE_VERSION,
        "workflow_template": {
            "id": workflow_template_id,
            "name": wf.get("name", "Workflow"),
            "description": wf.get("description", ""),
            "process": wf.get("crew_ai_process", "sequential"),
            "agent_template_ids": agent_template_ids,
            "task_template_ids": task_template_ids,
            "is_conversational": bool(wf.get("is_conversational", False)),
            "pre_packaged": False,
            "smart_workflow": False,
            "planning": False,
        },
        "agent_templates": agent_templates,
        "tool_templates": tool_templates,
        "mcp_templates": [],
        "task_templates": task_templates,
    }
    return payload, tool_dirs


def write_zip(payload: dict[str, Any], tool_dirs: dict[str, Path], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dir_markers: set[str] = set()

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = json.dumps(payload, indent=2)
        zf.writestr("workflow_template.json", manifest)

        for folder_posix, source_dir in sorted(tool_dirs.items()):
            for path in sorted(source_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(source_dir)
                arcname = f"{folder_posix}/{rel.as_posix()}"
                parent = str(Path(arcname).parent)
                while parent and parent != ".":
                    dir_markers.add(parent + "/")
                    parent = str(Path(parent).parent)

        for marker in sorted(dir_markers):
            zf.writestr(marker, "")

        for folder_posix, source_dir in sorted(tool_dirs.items()):
            for path in sorted(source_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(source_dir)
                arcname = f"{folder_posix}/{rel.as_posix()}"
                zf.write(path, arcname)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Agent Studio workflow template ZIP")
    parser.add_argument("--collated", type=Path, default=DEFAULT_COLLATED)
    parser.add_argument("--artifact-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.collated.is_file():
        print(f"Collated input not found: {args.collated}", file=sys.stderr)
        return 1

    collated = json.loads(args.collated.read_text(encoding="utf-8"))
    payload, tool_dirs = build_template(collated, args.artifact_root)
    write_zip(payload, tool_dirs, args.output)

    wf = payload["workflow_template"]
    print(f"Wrote {args.output}")
    print(f"  workflow: {wf['name']}")
    print(f"  agents: {len(payload['agent_templates'])}")
    print(f"  tasks: {len(payload['task_templates'])}")
    print(f"  tools: {len(payload['tool_templates'])}")
    print("Import in Agent Studio: Workflows → Templates → Import Template")
    return 0


if __name__ == "__main__":
    sys.exit(main())

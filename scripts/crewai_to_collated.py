#!/usr/bin/env python3
"""
Phase 0: Convert CrewAI YAML config (agents.yaml + tasks.yaml) to CollatedInput skeleton.

Reads agent/task definitions from a CrewAI project config directory and a crew spec
that defines workflow metadata, agent order, task order, and tool assignments.
Emits workflow.yaml, collated_input.json, and stub tool directories for validate/deploy.

Usage:
  python scripts/crewai_to_collated.py \\
    --config-dir /path/to/crew_hybrid/config \\
    --crew-spec converters/crew_specs/crew_hybrid_agentic.yaml \\
    -o examples/crew_hybrid_agentic
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    import yaml
except ImportError:
    print("Install PyYAML: pip install PyYAML", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent

STUB_REQUIREMENTS = "pydantic>=2.0.0\n"

STUB_TOOL_PY = '''\
"""
Stub tool for Phase 0 CollatedInput scaffold.

CrewAI source tool: {tool_name}
Replace run_tool() with ported logic from the CrewAI @tool implementation.
"""

from __future__ import annotations

import argparse
import json

from pydantic import BaseModel, Field


class UserParameters(BaseModel):
    """Tool configuration (paths, API keys) — populate in Phase 1+."""
    pass


class ToolParameters(BaseModel):
    """Arguments supplied by the agent when calling this tool."""
    input_text: str = Field(
        default="",
        description="Placeholder parameter — replace with CrewAI tool signature in Phase 1",
    )


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    return (
        "STUB [{tool_name}]: not implemented. "
        "Port from CrewAI toolkit in Phase 1. "
        f"input_text={{args.input_text!r}}"
    )


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


def new_id() -> str:
    return str(uuid4())


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # Collapse YAML folded-block extra whitespace while keeping sentence breaks.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def title_from_key(key: str) -> str:
    return key.replace("_", " ").title()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "workflow"


def collect_tool_names(crew_spec: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for agent in crew_spec.get("agents", []):
        for tool in agent.get("tools", []):
            if tool not in seen:
                seen.add(tool)
                ordered.append(tool)
    return ordered


def build_collated_input(
    agents_cfg: dict[str, Any],
    tasks_cfg: dict[str, Any],
    crew_spec: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return (collated_input dict, maps tool_name -> tool_instance_id)."""
    wf_meta = crew_spec["workflow"]
    llm_meta = crew_spec.get("language_model", {})
    llm_id = new_id()

    workflow_slug = wf_meta.get("slug") or slugify(wf_meta["name"])
    tool_name_to_id: dict[str, str] = {}
    tool_instances: list[dict[str, Any]] = []

    for tool_name in collect_tool_names(crew_spec):
        tool_id = new_id()
        tool_name_to_id[tool_name] = tool_id
        folder = f"studio-data/workflows/{workflow_slug}/tools/{tool_name}"
        tool_instances.append(
            {
                "id": tool_id,
                "name": title_from_key(tool_name),
                "python_code_file_name": "tool.py",
                "python_requirements_file_name": "requirements.txt",
                "source_folder_path": folder,
                "tool_metadata": json.dumps(
                    {"user_params": [], "user_params_metadata": {}, "status": "phase0_stub"}
                ),
                "tool_image_uri": None,
                "is_venv_tool": True,
            }
        )

    agent_key_to_id: dict[str, str] = {}
    agents: list[dict[str, Any]] = []

    for agent_entry in crew_spec.get("agents", []):
        key = agent_entry["key"]
        if key not in agents_cfg:
            raise KeyError(f"Agent key '{key}' not found in agents.yaml")
        cfg = agents_cfg[key]
        agent_id = new_id()
        agent_key_to_id[key] = agent_id
        tool_ids = [tool_name_to_id[t] for t in agent_entry.get("tools", [])]
        agents.append(
            {
                "id": agent_id,
                "name": title_from_key(key),
                "llm_provider_model_id": llm_id,
                "crew_ai_role": normalize_text(cfg.get("role", "")),
                "crew_ai_backstory": normalize_text(cfg.get("backstory", "")),
                "crew_ai_goal": normalize_text(cfg.get("goal", "")),
                "crew_ai_allow_delegation": False,
                "crew_ai_verbose": True,
                "crew_ai_cache": True,
                "crew_ai_temperature": 0.2,
                "crew_ai_max_iter": 15,
                "tool_instance_ids": tool_ids,
                "mcp_instance_ids": [],
                "agent_image_uri": None,
            }
        )

    tasks: list[dict[str, Any]] = []
    task_ids: list[str] = []

    for task_entry in crew_spec.get("tasks", []):
        key = task_entry["key"]
        agent_key = task_entry["agent"]
        if key not in tasks_cfg:
            raise KeyError(f"Task key '{key}' not found in tasks.yaml")
        if agent_key not in agent_key_to_id:
            raise KeyError(f"Task '{key}' references unknown agent '{agent_key}'")
        cfg = tasks_cfg[key]
        task_id = new_id()
        task_ids.append(task_id)
        tasks.append(
            {
                "id": task_id,
                "description": normalize_text(cfg.get("description", "")),
                "expected_output": normalize_text(cfg.get("expected_output", "")),
                "assigned_agent_id": agent_key_to_id[agent_key],
            }
        )

    agent_ids = [agent_key_to_id[a["key"]] for a in crew_spec.get("agents", [])]

    collated = {
        "default_language_model_id": llm_id,
        "language_models": [
            {
                "model_id": llm_id,
                "model_name": llm_meta.get("model_name", "gpt-4o"),
                "generation_config": {
                    "max_new_tokens": 4096,
                    "temperature": 0.2,
                    "do_sample": True,
                },
            }
        ],
        "tool_instances": tool_instances,
        "mcp_instances": [],
        "agents": agents,
        "tasks": tasks,
        "workflow": {
            "id": new_id(),
            "name": wf_meta["name"],
            "description": normalize_text(wf_meta.get("description", "")),
            "crew_ai_process": wf_meta.get("crew_ai_process", "sequential"),
            "agent_ids": agent_ids,
            "task_ids": task_ids,
            "manager_agent_id": None,
            "llm_provider_model_id": None,
            "is_conversational": bool(wf_meta.get("is_conversational", False)),
        },
    }
    return collated, tool_name_to_id


def write_stub_tools(output_root: Path, collated: dict[str, Any]) -> None:
    for tool in collated["tool_instances"]:
        folder = output_root / tool["source_folder_path"]
        folder.mkdir(parents=True, exist_ok=True)
        tool_slug = folder.name
        (folder / "tool.py").write_text(
            STUB_TOOL_PY.format(tool_name=tool_slug),
            encoding="utf-8",
        )
        (folder / "requirements.txt").write_text(STUB_REQUIREMENTS, encoding="utf-8")


def write_artifact(output_root: Path, collated: dict[str, Any]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    workflow_yaml = output_root / "workflow.yaml"
    workflow_yaml.write_text(
        yaml.dump(
            {"type": "collated_input", "input": "collated_input.json"},
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    collated_path = output_root / "collated_input.json"
    collated_path.write_text(json.dumps(collated, indent=2), encoding="utf-8")
    write_stub_tools(output_root, collated)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert CrewAI YAML config to CollatedInput skeleton (Phase 0)",
    )
    parser.add_argument(
        "--config-dir",
        required=True,
        type=Path,
        help="Directory containing agents.yaml and tasks.yaml",
    )
    parser.add_argument(
        "--crew-spec",
        required=True,
        type=Path,
        help="Crew spec YAML (workflow, agent order, tasks, tool assignments)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=Path,
        help="Output directory for workflow.yaml + collated_input.json + studio-data/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print collated_input.json to stdout instead of writing files",
    )
    args = parser.parse_args()

    config_dir = args.config_dir.resolve()
    agents_path = config_dir / "agents.yaml"
    tasks_path = config_dir / "tasks.yaml"
    for path in (agents_path, tasks_path, args.crew_spec):
        if not path.is_file():
            print(f"Missing file: {path}", file=sys.stderr)
            return 1

    agents_cfg = load_yaml(agents_path)
    tasks_cfg = load_yaml(tasks_path)
    crew_spec = load_yaml(args.crew_spec.resolve())

    try:
        collated, _ = build_collated_input(agents_cfg, tasks_cfg, crew_spec)
    except (KeyError, ValueError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(collated, indent=2))
        return 0

    write_artifact(args.output.resolve(), collated)
    print(f"Wrote CollatedInput artifact to {args.output.resolve()}")
    print(f"  Agents: {len(collated['agents'])}")
    print(f"  Tasks: {len(collated['tasks'])}")
    print(f"  Tools (stub): {len(collated['tool_instances'])}")
    print("Next: python scripts/validate.py --root", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

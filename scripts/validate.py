#!/usr/bin/env python3
"""Validate CollatedInput workflow artifact before deploy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_TOP_LEVEL = ("workflow.yaml", "collated_input.json", "studio-data")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_collated_input(data: dict) -> list[str]:
    errors: list[str] = []
    required_keys = {
        "default_language_model_id",
        "language_models",
        "tool_instances",
        "mcp_instances",
        "agents",
        "tasks",
        "workflow",
    }
    missing = required_keys - set(data)
    if missing:
        errors.append(f"collated_input.json missing keys: {sorted(missing)}")
        return errors

    workflow = data["workflow"]
    for field in ("id", "name", "crew_ai_process", "is_conversational"):
        if field not in workflow:
            errors.append(f"workflow.{field} is required")

    agent_ids = {a["id"] for a in data["agents"]}
    task_ids = {t["id"] for t in data["tasks"]}
    tool_ids = {t["id"] for t in data["tool_instances"]}

    for agent in data["agents"]:
        for tid in agent.get("tool_instance_ids", []):
            if tid not in tool_ids:
                errors.append(f"agent {agent['id']} references unknown tool {tid}")

    for task in data["tasks"]:
        aid = task.get("assigned_agent_id")
        if aid and aid not in agent_ids:
            errors.append(f"task {task['id']} references unknown agent {aid}")

    for tool in data["tool_instances"]:
        folder = REPO_ROOT / tool["source_folder_path"]
        code_file = folder / tool["python_code_file_name"]
        req_file = folder / tool["python_requirements_file_name"]
        if not code_file.is_file():
            errors.append(f"Missing tool code: {code_file}")
        if not req_file.is_file():
            errors.append(f"Missing tool requirements: {req_file}")

    if workflow.get("agent_ids"):
        for aid in workflow["agent_ids"]:
            if aid not in agent_ids:
                errors.append(f"workflow.agent_ids references unknown agent {aid}")

    if workflow.get("task_ids"):
        for tid in workflow["task_ids"]:
            if tid not in task_ids:
                errors.append(f"workflow.task_ids references unknown task {tid}")

    default_llm = data["default_language_model_id"]
    llm_ids = {m["model_id"] for m in data["language_models"]}
    if default_llm not in llm_ids:
        errors.append(f"default_language_model_id {default_llm} not in language_models")

    return errors


def main() -> int:
    errors: list[str] = []

    for name in REQUIRED_TOP_LEVEL:
        if not (REPO_ROOT / name).exists():
            errors.append(f"Missing required path at repo root: {name}")

    workflow_yaml = REPO_ROOT / "workflow.yaml"
    if workflow_yaml.is_file():
        import yaml

        meta = yaml.safe_load(workflow_yaml.read_text(encoding="utf-8"))
        if meta.get("type") != "collated_input":
            errors.append('workflow.yaml type must be "collated_input"')
        input_file = meta.get("input")
        if input_file and not (REPO_ROOT / input_file).is_file():
            errors.append(f"workflow.yaml input file not found: {input_file}")

    collated_path = REPO_ROOT / "collated_input.json"
    if collated_path.is_file():
        try:
            errors.extend(validate_collated_input(load_json(collated_path)))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in collated_input.json: {exc}")

    if errors:
        print("Validation FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

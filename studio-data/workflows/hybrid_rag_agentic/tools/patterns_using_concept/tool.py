"""List design patterns linked to a concept in the graph (e.g. RAG, reflection)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

_TOOL_FILE = Path(__file__)
# Agent Studio sandboxes mount only the tool directory at /tool; vendored lib lives alongside tool.py.
sys.path.insert(0, str(_TOOL_FILE.resolve().parent))
from tool_runtime import HybridUserParameters, build_toolkit


class UserParameters(HybridUserParameters):
    pass


class ToolParameters(BaseModel):
    concept_name: str = Field(description="Concept name to look up in the knowledge graph")


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    toolkit = build_toolkit(config, _TOOL_FILE)
    return toolkit.patterns_using_concept(args.concept_name)


OUTPUT_KEY = "tool_output"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True)
    parser.add_argument("--tool-params", required=True)
    cli = parser.parse_args()
    try:
        config = UserParameters(**json.loads(cli.user_params))
        params = ToolParameters(**json.loads(cli.tool_params))
        print(OUTPUT_KEY, run_tool(config, params))
    except Exception as exc:
        print(OUTPUT_KEY, json.dumps({"error": str(exc), "type": type(exc).__name__}))
        raise SystemExit(0)

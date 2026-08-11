"""
Stub tool for Phase 0 CollatedInput scaffold.

CrewAI source tool: reflect_on_hybrid_retrieval
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
        "STUB [reflect_on_hybrid_retrieval]: not implemented. "
        "Port from CrewAI toolkit in Phase 1. "
        f"input_text={args.input_text!r}"
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

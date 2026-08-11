"""
Calculator tool for Agent Studio custom workflow (IaC).
Performs basic arithmetic: +, -, *, /
"""

from pydantic import BaseModel, Field
from typing import Literal
import json
import argparse


class UserParameters(BaseModel):
    """Static configuration (API keys, etc.) — none required for this tool."""
    pass


class ToolParameters(BaseModel):
    """Arguments the LLM supplies when calling this tool."""
    a: float = Field(description="first number")
    b: float = Field(description="second number")
    op: Literal["+", "-", "*", "/"] = Field(description="arithmetic operator")


def _calculate(a: float, b: float, op: str) -> float:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ValueError("Division by zero is not allowed.")
        return a / b
    raise ValueError(f"Unsupported operator: {op}")


def run_tool(config: UserParameters, args: ToolParameters) -> str:
    result = _calculate(args.a, args.b, args.op)
    return f"{args.a} {args.op} {args.b} = {result}"


OUTPUT_KEY = "tool_output"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True, help="JSON string for tool configuration")
    parser.add_argument("--tool-params", required=True, help="JSON string for tool arguments")
    cli_args = parser.parse_args()

    config = UserParameters(**json.loads(cli_args.user_params))
    params = ToolParameters(**json.loads(cli_args.tool_params))
    output = run_tool(config, params)
    print(OUTPUT_KEY, output)

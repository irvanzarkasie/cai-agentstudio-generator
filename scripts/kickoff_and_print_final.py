#!/usr/bin/env python3
"""Kick off workflow and print final answer excerpt from event trace."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--app-url", required=True)
    parser.add_argument("--query", default="Enterprise RAG")
    parser.add_argument("--project-id", default="q0zf-3nb7-haf2-ze2p")
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()

    wb = os.environ.get("CAI_WORKBENCH_HOST", "").rstrip("/")
    key = os.environ.get("CDSW_APIV2_KEY", "")
    if not wb or not key:
        print("Set CAI_WORKBENCH_HOST and CDSW_APIV2_KEY", file=sys.stderr)
        return 1

    verify = not args.insecure
    h = {"Authorization": f"Bearer {key}"}
    domain = wb.replace("https://", "").replace("http://", "")

    rm = requests.get(
        f"{wb}/api/v2/projects/{args.project_id}/models/{args.model_id}",
        headers=h,
        verify=verify,
        timeout=60,
    )
    rm.raise_for_status()
    model_url = f"https://modelservice.{domain}/model?accessKey={rm.json()['access_key']}"

    payload = {
        "request": {
            "action_type": "kickoff",
            "kickoff_inputs": base64.b64encode(
                json.dumps({"query": args.query}).encode()
            ).decode(),
        }
    }
    kr = requests.post(
        model_url,
        json=payload,
        headers={**h, "Content-Type": "application/json"},
        verify=verify,
        timeout=120,
    )
    kr.raise_for_status()
    trace_id = kr.json().get("response", {}).get("trace_id")
    print(f"trace_id: {trace_id}\nquery: {args.query}\n")

    events: list[dict] = []
    for i in range(60):
        er = requests.get(
            f"{args.app_url.rstrip('/')}/api/workflow/events",
            params={"trace_id": trace_id},
            headers=h,
            verify=verify,
            timeout=60,
        )
        events = er.json().get("events", [])
        if any(e.get("type") == "crew_kickoff_completed" for e in events):
            break
        time.sleep(10)

    final = ""
    for e in reversed(events):
        if e.get("type") == "task_completed" and e.get("outout"):
            final = e["outout"]
            break
        if e.get("type") == "llm_call_completed":
            resp = e.get("response", "")
            if "Final Answer:" in resp:
                final = resp.split("Final Answer:", 1)[-1].strip()
                break

    tool_count = sum(1 for e in events if e.get("type") == "tool_usage_finished")
    print(f"events: {len(events)}, tool calls: {tool_count}\n")
    print("=" * 60)
    print(final[:8000] if final else "(no final output captured)")
    print("=" * 60)

    checks = {
        "has_section_1": "Recommended Patterns to Implement Based on Reference" in final,
        "has_section_2": "Production Considerations, Tradeoffs, and Validations" in final,
        "out_of_scope": "Out of Scope" in final,
        "mentions_agent_studio_stack": any(
            x in final.lower()
            for x in ("agent studio", "graph.json", "bundled book", "chroma")
        ),
        "mentions_pattern_number": "Pattern" in final and any(c.isdigit() for c in final),
    }
    print("\nchecks:", json.dumps(checks, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

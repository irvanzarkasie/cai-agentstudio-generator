#!/usr/bin/env python3
"""Kick off deployed Hybrid RAG workflow and inspect event trace for tool failures."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deployed workflow tool trace")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--app-url", required=True)
    parser.add_argument("--project-id", default="q0zf-3nb7-haf2-ze2p")
    parser.add_argument("--query", default="enterprise RAG with reranking and citations")
    parser.add_argument("--polls", type=int, default=40)
    parser.add_argument("--interval", type=int, default=15)
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
    print(f"trace_id: {trace_id}")

    all_events: list[dict] = []
    for i in range(args.polls):
        er = requests.get(
            f"{args.app_url.rstrip('/')}/api/workflow/events",
            params={"trace_id": trace_id},
            headers=h,
            verify=verify,
            timeout=60,
        )
        all_events = er.json().get("events", [])
        if any(e.get("type") == "crew_kickoff_completed" for e in all_events):
            print(f"completed after poll {i + 1} ({len(all_events)} events)")
            break
        time.sleep(args.interval)

    tool_finishes = [e for e in all_events if e.get("type") == "tool_usage_finished"]
    print(f"tool calls finished: {len(tool_finishes)}")
    for e in tool_finishes:
        t0 = datetime.fromisoformat(e["started_at"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(e["finished_at"].replace("Z", "+00:00"))
        print(f"  {e['tool_name']}: {(t1 - t0).total_seconds():.2f}s")

    errors: list[str] = []
    success: list[str] = []
    for e in all_events:
        if e.get("type") != "llm_call_started":
            continue
        for m in e.get("messages", []):
            content = m.get("content", "")
            if "Observation:" not in content:
                continue
            obs = content.split("Observation:")[-1].strip()
            if obs.startswith('{"error"'):
                errors.append(obs[:400])
            elif any(k in obs for k in ("pattern_number", "recommended_stack", "technical_text")):
                success.append(obs[:400])

    print(f"tool error observations: {len(errors)}")
    if errors:
        print("first error:", errors[0])
    print(f"successful tool observations: {len(success)}")
    for sample in success[:3]:
        print("sample:", sample[:300])
        print("---")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

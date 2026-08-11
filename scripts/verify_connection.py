#!/usr/bin/env python3
"""Verify CML and Agent Studio API connectivity."""

from __future__ import annotations

import os
import sys

import requests


def check(name: str, url: str, headers: dict, method: str = "GET") -> bool:
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=30, verify=False)
        else:
            resp = requests.post(url, headers=headers, timeout=30, verify=False)
        ok = resp.status_code == 200
        snippet = (resp.text or "")[:200].replace("\n", " ")
        print(f"[{'OK' if ok else 'FAIL'}] {name}: HTTP {resp.status_code} — {snippet}")
        return ok
    except requests.RequestException as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def main() -> int:
    workbench = os.environ.get("CAI_WORKBENCH_HOST", "").rstrip("/")
    agent_studio = os.environ.get("AGENT_STUDIO_URL", "").rstrip("/")
    key = os.environ.get("CDSW_APIV2_KEY", "")

    if not all([workbench, agent_studio, key]):
        print("Set CAI_WORKBENCH_HOST, AGENT_STUDIO_URL, CDSW_APIV2_KEY", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {key}"}
    results = [
        check("Workbench projects", f"{workbench}/api/v2/projects?page_size=5", headers),
        check("Agent Studio listWorkflows", f"{agent_studio}/api/grpc/listWorkflows", headers),
        check("Agent Studio default model", f"{agent_studio}/api/grpc/getStudioDefaultModel", headers),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

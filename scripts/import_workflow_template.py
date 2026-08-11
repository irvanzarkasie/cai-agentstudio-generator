#!/usr/bin/env python3
"""
Upload a workflow template ZIP to the Agent Studio project and import it via gRPC.

Requires environment variables:
  CAI_WORKBENCH_HOST, AGENT_STUDIO_URL, CDSW_APIV2_KEY
Optional:
  CAI_PROJECT_ID (default: discovered Agent Studio project)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_agent_studio_project(host: str, api_key: str, verify: bool) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(f"{host.rstrip('/')}/api/v2/projects", headers=headers, timeout=60, verify=verify)
    resp.raise_for_status()
    for project in resp.json().get("projects", []):
        name = (project.get("name") or "").casefold()
        if "agent studio" in name:
            return project["id"]
    raise RuntimeError("Could not find Agent Studio project; set CAI_PROJECT_ID")


def upload_zip(
    workbench_host: str,
    project_id: str,
    api_key: str,
    zip_path: Path,
    target_name: str,
    verify: bool,
) -> str:
    """Upload ZIP to project root; returns filename as stored on the workbench."""
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{workbench_host.rstrip('/')}/api/v2/projects/{project_id}/files"
    with zip_path.open("rb") as handle:
        resp = requests.post(
            url,
            headers=headers,
            files={"file": (target_name, handle, "application/zip")},
            timeout=300,
            verify=verify,
        )
    resp.raise_for_status()
    return target_name


def import_template(agent_studio_url: str, api_key: str, absolute_path: str, verify: bool) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{agent_studio_url.rstrip('/')}/api/grpc/importWorkflowTemplate"
    resp = requests.post(url, headers=headers, json={"file_path": absolute_path}, timeout=300, verify=verify)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload and import workflow template ZIP")
    parser.add_argument(
        "--zip",
        type=Path,
        default=REPO_ROOT / "dist" / "hybrid_rag_agentic_workflow_template.zip",
        help="Workflow template ZIP path",
    )
    parser.add_argument(
        "--remote-name",
        default="hybrid_rag_agentic_workflow_template.zip",
        help="Filename to use on the Agent Studio project (project root)",
    )
    parser.add_argument("--project-id", default=os.environ.get("CAI_PROJECT_ID"))
    parser.add_argument("--workbench-host", default=os.environ.get("CAI_WORKBENCH_HOST"))
    parser.add_argument("--agent-studio-url", default=os.environ.get("AGENT_STUDIO_URL"))
    parser.add_argument("--api-key", default=os.environ.get("CDSW_APIV2_KEY"))
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--upload-only", action="store_true")
    args = parser.parse_args()

    if not args.zip.is_file():
        print(f"ZIP not found: {args.zip}. Run scripts/collated_to_workflow_template.py first.", file=sys.stderr)
        return 1
    if not all([args.workbench_host, args.agent_studio_url, args.api_key]):
        print("Set CAI_WORKBENCH_HOST, AGENT_STUDIO_URL, CDSW_APIV2_KEY", file=sys.stderr)
        return 1

    verify = not args.insecure
    project_id = args.project_id or find_agent_studio_project(args.workbench_host, args.api_key, verify)

    print(f"Uploading {args.zip} as {args.remote_name}")
    stored_name = upload_zip(
        args.workbench_host, project_id, args.api_key, args.zip, args.remote_name, verify
    )

    absolute_path = f"/home/cdsw/{stored_name}"
    print(f"Uploaded. Absolute import path: {absolute_path}")
    if args.upload_only:
        print("Upload only — in Agent Studio UI use Import Template with:")
        print(f"  {stored_name}")
        return 0

    print("Importing template via Agent Studio API...")
    result = import_template(args.agent_studio_url, args.api_key, absolute_path, verify)
    template_id = result.get("id", result)
    print(f"Import OK — workflow template id: {template_id}")
    print("Open Agent Studio → Workflows → Templates → create workflow from template.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

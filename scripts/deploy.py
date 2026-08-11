#!/usr/bin/env python3
"""Deploy workflow to Agent Studio using GitHub target (DeploymentPayload)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Replace ${VAR} placeholders and inject secrets from environment."""
    github_url = os.environ.get("GITHUB_WORKFLOW_URL")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if github_url and config.get("workflow_target", {}).get("type") == "github":
        config["workflow_target"]["github_url"] = github_url

    llm_config = config.setdefault("deployment_config", {}).setdefault("llm_config", {})
    default_llm_id = None
    collated_path = REPO_ROOT / "collated_input.json"
    if collated_path.is_file():
        collated = json.loads(collated_path.read_text(encoding="utf-8"))
        default_llm_id = collated.get("default_language_model_id")

    if openai_key and default_llm_id:
        llm_config.setdefault(
            default_llm_id,
            {
                "api_key": openai_key,
                "api_base": "https://api.openai.com/v1",
                "provider_model": "gpt-4o-mini",
                "model_type": "OPENAI",
            },
        )

    return config


def deploy(config: dict[str, Any], agent_studio_url: str, api_key: str, verify_tls: bool = True) -> dict:
    endpoint = urljoin(agent_studio_url.rstrip("/") + "/", "api/grpc/deployWorkflow")
    body = {"deployment_payload": json.dumps(config)}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(endpoint, json=body, headers=headers, timeout=120, verify=verify_tls)
    resp.raise_for_status()
    return resp.json()


def list_deployed(agent_studio_url: str, api_key: str, verify_tls: bool = True) -> dict:
    endpoint = urljoin(agent_studio_url.rstrip("/") + "/", "api/grpc/listDeployedWorkflows")
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(endpoint, headers=headers, timeout=60, verify=verify_tls)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Agent Studio workflow (GitHub target)")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "deploy" / "deployment-config.example.json"),
        help="Deployment JSON config path",
    )
    parser.add_argument("--agent-studio-url", default=os.environ.get("AGENT_STUDIO_URL"))
    parser.add_argument("--api-key", default=os.environ.get("CDSW_APIV2_KEY"))
    parser.add_argument("--insecure", action="store_true", help="Skip TLS verification")
    parser.add_argument("--wait", type=int, default=0, help="Seconds to wait then list deployments")
    args = parser.parse_args()

    if not args.agent_studio_url:
        print("Set AGENT_STUDIO_URL or pass --agent-studio-url", file=sys.stderr)
        return 1
    if not args.api_key:
        print("Set CDSW_APIV2_KEY or pass --api-key", file=sys.stderr)
        return 1

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    config = apply_env_overrides(load_config(config_path))
    verify = not args.insecure

    print(f"Deploying from GitHub: {config.get('workflow_target', {}).get('github_url')}")
    print(f"Agent Studio: {args.agent_studio_url}")

    try:
        result = deploy(config, args.agent_studio_url, args.api_key, verify_tls=verify)
        print("Deploy request accepted:")
        print(json.dumps(result, indent=2))
    except requests.HTTPError as exc:
        print(f"Deploy failed: {exc}", file=sys.stderr)
        if exc.response is not None:
            print(exc.response.text, file=sys.stderr)
        return 1

    if args.wait > 0:
        print(f"Waiting {args.wait}s before listing deployments...")
        time.sleep(args.wait)
        try:
            listed = list_deployed(args.agent_studio_url, args.api_key, verify_tls=verify)
            print(json.dumps(listed, indent=2))
        except requests.HTTPError as exc:
            print(f"Could not list deployments: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())

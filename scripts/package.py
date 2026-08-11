#!/usr/bin/env python3
"""Build artifact.tar.gz matching Agent Studio packaging layout."""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def package(source_root: Path, output: Path) -> Path:
    staging = Path(tempfile.mkdtemp(prefix="as-artifact-"))
    try:
        shutil.copy2(source_root / "workflow.yaml", staging / "workflow.yaml")
        shutil.copy2(source_root / "collated_input.json", staging / "collated_input.json")
        shutil.copytree(source_root / "studio-data", staging / "studio-data")

        meta = yaml.safe_load((source_root / "workflow.yaml").read_text(encoding="utf-8"))
        input_name = meta.get("input", "collated_input.json")
        collated = json.loads((source_root / input_name).read_text(encoding="utf-8"))
        # sanity: ensure JSON is serializable
        json.dumps(collated)

        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, "w:gz") as tar:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    arcname = path.relative_to(staging).as_posix()
                    tar.add(path, arcname=arcname)

        return output
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Package workflow artifact")
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Artifact root containing workflow.yaml (default: repository root)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(REPO_ROOT / ".artifacts" / "artifact.tar.gz"),
        help="Output tar.gz path",
    )
    args = parser.parse_args()
    out = package(args.root.resolve(), Path(args.output))
    print(f"Packaged: {out}")


if __name__ == "__main__":
    main()

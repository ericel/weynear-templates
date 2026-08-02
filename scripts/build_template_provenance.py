#!/usr/bin/env python3
"""Generate a SLSA v1 predicate for a centrally built template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--builder-id", required=True)
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--started-on", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = {
        "_type": "https://slsa.dev/provenance/v1",
        "buildDefinition": {
            "buildType": "https://registry.automations.weynear.com/buildtypes/central-docker-v1",
            "externalParameters": {
                "template": f"{args.publisher}/{args.name}",
                "platform": "linux/amd64",
                "sourcePath": args.source_path,
            },
            "internalParameters": {"invocationId": args.invocation_id},
            "resolvedDependencies": [
                {
                    "uri": f"git+{args.source_repository}@{args.source_commit}",
                    "digest": {"gitCommit": args.source_commit},
                }
            ],
        },
        "runDetails": {
            "builder": {"id": args.builder_id},
            "metadata": {
                "invocationId": args.invocation_id,
                "startedOn": args.started_on,
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""List or resolve source-only preview recipes for secretless builds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "registry" / "recipes"


def pending_builds() -> list[dict[str, str]]:
    requests = []
    for path in sorted(RECIPES.glob("*/*/*/template.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        metadata = document.get("metadata") or {}
        spec = document.get("spec") or {}
        if metadata.get("status") != "preview" or spec.get("artifact") is not None:
            continue
        source = spec.get("source") or {}
        build = spec.get("build") or {}
        repository = str(source.get("repository") or "")
        parsed = urlparse(repository)
        slug = parsed.path.strip("/")
        requests.append(
            {
                "publisher": str(metadata.get("publisher") or ""),
                "name": str(metadata.get("name") or ""),
                "version": str(metadata.get("version") or ""),
                "repository": repository,
                "repository_slug": slug,
                "commit": str(source.get("commit") or ""),
                "context": str(build.get("context") or ""),
                "dockerfile": str(build.get("dockerfile") or ""),
                "recipe": path.relative_to(RECIPES.parents[1]).as_posix(),
            }
        )
    return requests


def select(publisher: str, name: str, version: str) -> dict[str, str]:
    matches = [
        item
        for item in pending_builds()
        if (item["publisher"], item["name"], item["version"])
        == (publisher, name, version)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one pending build for {publisher}/{name}@{version}; found {len(matches)}"
        )
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publisher")
    parser.add_argument("--name")
    parser.add_argument("--version")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    if any((args.publisher, args.name, args.version)):
        if not all((args.publisher, args.name, args.version)):
            raise SystemExit("publisher, name, and version must be supplied together")
        request = select(args.publisher, args.name, args.version)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                for key, value in request.items():
                    output.write(f"{key}={value}\n")
        else:
            print(json.dumps(request, sort_keys=True))
        return
    print(json.dumps(pending_builds(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

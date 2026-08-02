#!/usr/bin/env python3
"""Apply a trusted builder result to one preview template recipe."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


COMMIT = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def _require(pattern: re.Pattern[str], value: str, label: str) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"invalid {label}: {value}")
    return value


def promote(
    registry_root: Path,
    *,
    publisher: str,
    name: str,
    version: str,
    source_commit: str,
    artifact_digest: str,
) -> Path:
    _require(IDENTIFIER, publisher, "publisher")
    _require(IDENTIFIER, name, "template name")
    _require(SEMVER, version, "template version")
    _require(COMMIT, source_commit, "source commit")
    _require(DIGEST, artifact_digest, "artifact digest")

    recipe_path = (
        registry_root
        / "recipes"
        / publisher
        / name
        / version
        / "template.yaml"
    )
    if not recipe_path.is_file():
        raise ValueError(f"template recipe does not exist: {recipe_path}")
    document: Any = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"template recipe must be an object: {recipe_path}")
    metadata = document.get("metadata")
    spec = document.get("spec")
    if not isinstance(metadata, dict) or not isinstance(spec, dict):
        raise ValueError(f"template recipe has no metadata/spec: {recipe_path}")
    identity = (
        metadata.get("publisher"),
        metadata.get("name"),
        metadata.get("version"),
    )
    if identity != (publisher, name, version):
        raise ValueError("template path and metadata identity disagree")
    current_status = str(metadata.get("status") or "")
    if current_status not in {"preview", "approved"}:
        raise ValueError(
            f"only preview templates can be promoted; status is {current_status}"
        )
    source = spec.get("source")
    artifact = spec.get("artifact")
    if not isinstance(source, dict):
        raise ValueError("template source must be an object")
    if artifact is None:
        publisher_path = registry_root / "publishers" / f"{publisher}.yaml"
        publisher_document: Any = yaml.safe_load(
            publisher_path.read_text(encoding="utf-8")
        )
        prefix = str(
            publisher_document["spec"]["artifact_registry"]["repository_prefix"]
        )
        image = f"{prefix}{name}"
        artifact = {
            "uri": f"{image}@{artifact_digest}",
            "digest": artifact_digest,
            "media_type": "application/vnd.oci.image.manifest.v1+json",
            "platform": {"os": "linux", "architecture": "amd64"},
        }
        spec["artifact"] = artifact
    elif isinstance(artifact, dict):
        uri = str(artifact.get("uri") or "")
        image, separator, _ = uri.partition("@")
        expected_suffix = f"/{publisher}/{name}"
        if separator != "@" or not image.endswith(expected_suffix):
            raise ValueError("artifact URI does not match template identity")
    else:
        raise ValueError("template artifact must be an object")

    source["commit"] = source_commit
    artifact["digest"] = artifact_digest
    artifact["uri"] = f"{image}@{artifact_digest}"
    metadata["status"] = "approved"
    recipe_path.write_text(
        yaml.safe_dump(document, sort_keys=False),
        encoding="utf-8",
    )
    return recipe_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-root", type=Path, default=Path("registry"))
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifact-digest", required=True)
    args = parser.parse_args()
    path = promote(
        args.registry_root,
        publisher=args.publisher,
        name=args.name,
        version=args.version,
        source_commit=args.source_commit,
        artifact_digest=args.artifact_digest,
    )
    print(f"promoted {args.publisher}/{args.name}@{args.version}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

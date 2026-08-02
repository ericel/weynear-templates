#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"
PUBLISHERS = REGISTRY / "publishers"
RECIPES = REGISTRY / "recipes"
CATALOG = REGISTRY / "catalog.json"
CATALOG_VERSION = REGISTRY / "catalog-version.txt"
SCHEMAS = ROOT / "schemas"

IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
COMMIT = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
GAR_URI = re.compile(
    r"^(?P<host>[a-z0-9-]+-docker\.pkg\.dev)/"
    r"(?P<project>[a-z0-9-]+)/(?P<repository>[a-z0-9-]+)/"
    r"(?P<image>[a-z0-9-]+/[a-z0-9-]+)@(?P<digest>sha256:[a-f0-9]{64})$"
)
PLACEHOLDER = re.compile(r"\$\{([^{}]+)\}")
STATIC_PLACEHOLDERS = {"DISPLAY_NAME", "BOT_ID"}
LEGACY_UNSCOPED_REFS = {
    ("weynear", "sports-live-scores", version)
    for version in ("1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.4.0", "2.0.0")
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a YAML object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def validator(name: str) -> Draft202012Validator:
    schema = load_json(SCHEMAS / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


PUBLISHER_VALIDATOR = validator("publisher.schema.json")
TEMPLATE_VALIDATOR = validator("template.schema.json")
MANIFEST_VALIDATOR = validator("manifest.schema.json")
CATALOG_VALIDATOR = validator("catalog.schema.json")


def validate_schema(
    schema_validator: Draft202012Validator,
    value: dict[str, Any],
    path: Path,
) -> None:
    errors = sorted(
        schema_validator.iter_errors(value),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path)
    suffix = f" at {location}" if location else ""
    raise ValueError(f"{path}: {error.message}{suffix}")


def canonical_github_repository(value: str, label: str) -> tuple[str, str]:
    parsed = urlparse(value)
    segments = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "github.com"
        or parsed.query
        or parsed.fragment
        or len(segments) != 2
    ):
        raise ValueError(f"{label}: expected canonical HTTPS GitHub repository")
    canonical = f"https://github.com/{segments[0].lower()}/{segments[1].lower()}"
    if value != canonical:
        raise ValueError(f"{label}: repository URL must be lowercase and canonical")
    return canonical, segments[0].lower()


def safe_relative_path(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or "\\" in value
        or str(path) != value
    ):
        raise ValueError(f"{label}: expected normalized repository-relative path")
    return value


def load_publishers() -> dict[str, dict[str, Any]]:
    publishers: dict[str, dict[str, Any]] = {}
    for path in sorted(PUBLISHERS.glob("*.yaml")):
        document = load_yaml(path)
        validate_schema(PUBLISHER_VALIDATOR, document, path)
        publisher_id = document["metadata"]["publisher"]
        if path != PUBLISHERS / f"{publisher_id}.yaml":
            raise ValueError(f"{path}: publisher identity does not match path")
        github = document["spec"]["github"]
        owner = github["owner"].lower()
        repositories = []
        for repository in github["repositories"]:
            canonical, repository_owner = canonical_github_repository(
                repository,
                f"{path}: spec.github.repositories",
            )
            if repository_owner != owner:
                raise ValueError(
                    f"{path}: source repository is outside the protected GitHub owner"
                )
            repositories.append(canonical)
        if len(repositories) != len(set(repositories)):
            raise ValueError(f"{path}: duplicate source repository")
        document["_repositories"] = frozenset(repositories)
        document["_digest"] = sha256(
            canonical_bytes(
                {
                    key: value
                    for key, value in document.items()
                    if not key.startswith("_")
                }
            )
        )
        if publisher_id in publishers:
            raise ValueError(f"{path}: duplicate publisher")
        publishers[publisher_id] = document
    if not publishers:
        raise ValueError("registry has no publisher records")
    return publishers


def placeholder_sample(
    placeholder: str,
    configuration: dict[str, dict[str, Any]],
    bindings: dict[str, dict[str, Any]],
) -> str:
    if placeholder == "DISPLAY_NAME":
        return "Registry Validation"
    if placeholder == "BOT_ID":
        return "bot_registry_validation"
    if placeholder.startswith("CONFIG:"):
        key = placeholder.partition(":")[2]
        definition = configuration.get(key)
        if definition is None:
            raise ValueError(f"undeclared configuration placeholder: {placeholder}")
        return {
            "integer": "1",
            "boolean": "true",
            "url": "https://provider.example/v1",
        }.get(definition["type"], "registry-validation")
    parts = placeholder.split(":")
    if len(parts) == 3 and parts[0] == "BINDING":
        binding_id, field = parts[1], parts[2]
        binding = bindings.get(binding_id)
        if binding is None:
            raise ValueError(f"undeclared binding placeholder: {placeholder}")
        if field == "SCOPE" and binding["kind"] == "post_audience":
            return binding["default_scope"]
        if field == "RESOURCE_ID":
            return "aud_registry_validation"
    raise ValueError(f"unsupported installation placeholder: {placeholder}")


def render_manifest(
    raw_text: str,
    configuration_items: list[dict[str, Any]],
    binding_items: list[dict[str, Any]],
) -> dict[str, Any]:
    configuration = {item["key"]: item for item in configuration_items}
    bindings = {item["id"]: item for item in binding_items}

    def replace(match: re.Match[str]) -> str:
        return placeholder_sample(match.group(1), configuration, bindings)

    rendered = PLACEHOLDER.sub(replace, raw_text)
    document = yaml.safe_load(rendered)
    if not isinstance(document, dict):
        raise ValueError("rendered manifest must be an object")
    return document


def validate_manifest_semantics(
    document: dict[str, Any],
    bindings: list[dict[str, Any]],
    path: Path,
) -> None:
    validate_schema(MANIFEST_VALIDATOR, document, path)
    spec = document["spec"]
    destinations = spec["destinations"]
    destination_ids = [item["id"] for item in destinations]
    if len(destination_ids) != len(set(destination_ids)):
        raise ValueError(f"{path}: duplicate destination id")
    destination_by_id = {item["id"]: item for item in destinations}
    for binding in bindings:
        destination = destination_by_id.get(binding["manifest_destination"])
        if destination is None:
            raise ValueError(
                f"{path}: binding references an undeclared manifest destination"
            )
        expected_type = (
            "posts" if binding["kind"] == "post_audience" else "messages"
        )
        if destination["type"] != expected_type:
            raise ValueError(f"{path}: binding and destination kinds disagree")
    trigger_ids = [item["id"] for item in spec["triggers"]]
    if len(trigger_ids) != len(set(trigger_ids)):
        raise ValueError(f"{path}: duplicate trigger id")
    connection_ids = [item["id"] for item in spec["connections"]]
    if len(connection_ids) != len(set(connection_ids)):
        raise ValueError(f"{path}: duplicate connection id")


def validate_recipe(
    path: Path,
    publishers: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    recipe = load_yaml(path)
    validate_schema(TEMPLATE_VALIDATOR, recipe, path)
    metadata = recipe["metadata"]
    spec = recipe["spec"]
    publisher_id = metadata["publisher"]
    name = metadata["name"]
    version = metadata["version"]
    expected_path = RECIPES / publisher_id / name / version / "template.yaml"
    if path != expected_path:
        raise ValueError(f"{path}: recipe identity does not match path")
    publisher = publishers.get(publisher_id)
    if publisher is None:
        raise ValueError(f"{path}: publisher is not registered")

    source = spec["source"]
    repository, owner = canonical_github_repository(
        source["repository"],
        f"{path}: spec.source.repository",
    )
    if owner != publisher["spec"]["github"]["owner"].lower():
        raise ValueError(f"{path}: source owner does not match publisher authority")
    if repository not in publisher["_repositories"]:
        raise ValueError(f"{path}: source repository is not registered")
    if not COMMIT.fullmatch(source["commit"]) or source["commit"] == "0" * 40:
        raise ValueError(f"{path}: source commit must be a nonzero full Git SHA")
    source_path = safe_relative_path(source["path"], f"{path}: spec.source.path")

    build = spec.get("build")
    if build is not None:
        context_path = safe_relative_path(
            build["context"],
            f"{path}: spec.build.context",
        )
        dockerfile_path = safe_relative_path(
            build["dockerfile"],
            f"{path}: spec.build.dockerfile",
        )
        if context_path != source_path:
            raise ValueError(f"{path}: build context must equal spec.source.path")
        context = PurePosixPath(context_path)
        dockerfile = PurePosixPath(dockerfile_path)
        if dockerfile.parent != context and context not in dockerfile.parents:
            raise ValueError(f"{path}: Dockerfile must be inside the build context")

    artifact = spec.get("artifact")
    if artifact is None:
        if metadata["status"] != "preview":
            raise ValueError(f"{path}: approved/deprecated recipes require a trusted artifact")
        if build is None:
            raise ValueError(f"{path}: unbuilt preview recipes require spec.build")
    else:
        match = GAR_URI.fullmatch(artifact["uri"])
        if match is None:
            raise ValueError(f"{path}: artifact must be a digest-qualified GAR URI")
        if match.group("digest") != artifact["digest"]:
            raise ValueError(f"{path}: artifact URI and declared digest disagree")
        prefix = publisher["spec"]["artifact_registry"]["repository_prefix"]
        if (
            not artifact["uri"].startswith(prefix)
            or match.group("image") != f"{publisher_id}/{name}"
        ):
            raise ValueError(f"{path}: artifact is outside the publisher namespace")

    manifest_name = safe_relative_path(
        spec["manifest"],
        f"{path}: spec.manifest",
    )
    if PurePosixPath(manifest_name).name != manifest_name:
        raise ValueError(f"{path}: manifest must be in the version directory")
    manifest_path = path.parent / manifest_name
    if not manifest_path.is_file():
        raise ValueError(f"{path}: manifest does not exist")
    readme_path = path.parent / "README.md"
    if not readme_path.is_file():
        raise ValueError(f"{path}: template README does not exist")
    manifest_text = manifest_path.read_text(encoding="utf-8")
    rendered_manifest = render_manifest(
        manifest_text,
        spec["configuration"],
        spec["bindings"],
    )
    validate_manifest_semantics(rendered_manifest, spec["bindings"], manifest_path)
    manifest_digest = sha256(manifest_text.encode("utf-8"))

    # Source-only previews are accepted contributions, not installable catalog
    # entries. The trusted central builder promotes them with an OCI digest.
    if artifact is None:
        return None, manifest_text

    submission_id = str(metadata.get("submission_id") or "").strip()
    if not submission_id and (publisher_id, name, version) not in LEGACY_UNSCOPED_REFS:
        raise ValueError(f"{path}: metadata.submission_id is required for new versions")
    entry = {
        "publisher": publisher_id,
        "name": name,
        "version": version,
        "display_name": metadata["display_name"],
        "summary": metadata["summary"],
        "status": metadata["status"],
        "license": metadata["license"],
        "categories": metadata.get("categories", []),
        "tags": metadata.get("tags", []),
        "icon_url": metadata.get("icon_url", ""),
        "source": copy.deepcopy(source),
        "artifact": copy.deepcopy(artifact),
        "runtime_adapter": spec["runtime_adapter"],
        "bot_required": spec["bot_required"],
        "configuration": copy.deepcopy(spec["configuration"]),
        "bindings": copy.deepcopy(spec["bindings"]),
        "compatibility": copy.deepcopy(spec["compatibility"]),
        "moderation": copy.deepcopy(spec["moderation"]),
        "install_manifest": {
            "path": (
                f"manifests/{publisher_id}/{name}/{version}/manifest.yaml"
            ),
            "digest": manifest_digest,
        },
        "publisher_verification": {
            "publisher_record_digest": publisher["_digest"],
            "trusted_builders": publisher["spec"]["builders"],
            "required_attestations": publisher["spec"][
                "required_attestations"
            ],
            "signature": publisher["spec"]["signing"],
        },
        "recipe_digest": sha256(canonical_bytes(recipe)),
    }
    if submission_id:
        entry["submission_id"] = submission_id
    return entry, manifest_text


def catalog_version() -> int:
    raw = CATALOG_VERSION.read_text(encoding="utf-8").strip()
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError("registry/catalog-version.txt must be a positive integer")
    return int(raw)


def build_catalog() -> tuple[dict[str, Any], dict[str, str]]:
    publishers = load_publishers()
    entries: list[dict[str, Any]] = []
    manifests: dict[str, str] = {}
    for path in sorted(RECIPES.glob("*/*/*/template.yaml")):
        entry, manifest_text = validate_recipe(path, publishers)
        if entry is None:
            continue
        entries.append(entry)
        manifest_path = entry["install_manifest"]["path"]
        if manifest_path in manifests:
            raise ValueError(f"duplicate release manifest path: {manifest_path}")
        manifests[manifest_path] = manifest_text
    if not entries:
        raise ValueError("registry has no template recipes")
    identities = [
        (entry["publisher"], entry["name"], entry["version"])
        for entry in entries
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("registry has duplicate template coordinates")
    catalog = {
        "api_version": "registry.automations.weynear.com/catalog/v1",
        "catalog_version": catalog_version(),
        "templates_digest": sha256(canonical_bytes(entries)),
        "templates": entries,
    }
    validate_schema(CATALOG_VALIDATOR, catalog, CATALOG)
    return catalog, manifests


def rendered_catalog(catalog: dict[str, Any]) -> str:
    return json.dumps(catalog, indent=2, sort_keys=True) + "\n"


def write_release(
    release_dir: Path,
    catalog: dict[str, Any],
    manifests: dict[str, str],
) -> None:
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)
    release_dir.joinpath("catalog.json").write_text(
        rendered_catalog(catalog),
        encoding="utf-8",
    )
    release_dir.joinpath("catalog-version.txt").write_text(
        f"{catalog['catalog_version']}\n",
        encoding="utf-8",
    )
    for relative_path, text in manifests.items():
        target = release_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--release-dir", type=Path)
    parser.add_argument("--write-signing-payload", type=Path)
    args = parser.parse_args()

    catalog, manifests = build_catalog()
    rendered = rendered_catalog(catalog)
    if args.write:
        CATALOG.write_text(rendered, encoding="utf-8")
    else:
        if not CATALOG.is_file() or CATALOG.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "registry/catalog.json is stale; run scripts/build_catalog.py --write"
            )
    if args.release_dir:
        write_release(args.release_dir, catalog, manifests)
    if args.write_signing_payload:
        args.write_signing_payload.parent.mkdir(parents=True, exist_ok=True)
        args.write_signing_payload.write_bytes(canonical_bytes(catalog))
    print(
        f"validated {len(catalog['templates'])} template version(s); "
        f"catalog v{catalog['catalog_version']} "
        f"{catalog['templates_digest']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

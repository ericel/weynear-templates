from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from scripts import build_catalog as catalog
from scripts import check_immutability as immutability
from scripts import promote_template as promotion


def isolated_registry(tmp_path: Path, monkeypatch):
    registry = tmp_path / "registry"
    shutil.copytree(catalog.REGISTRY, registry)
    monkeypatch.setattr(catalog, "REGISTRY", registry)
    monkeypatch.setattr(catalog, "PUBLISHERS", registry / "publishers")
    monkeypatch.setattr(catalog, "RECIPES", registry / "recipes")
    monkeypatch.setattr(catalog, "CATALOG", registry / "catalog.json")
    monkeypatch.setattr(
        catalog,
        "CATALOG_VERSION",
        registry / "catalog-version.txt",
    )
    recipe = (
        registry
        / "recipes"
        / "weynear"
        / "sports-live-scores"
        / "1.0.0"
        / "template.yaml"
    )
    manifest = recipe.parent / "manifest.yaml"
    publisher = registry / "publishers" / "weynear.yaml"
    return registry, recipe, manifest, publisher


def mutate_yaml(path: Path, mutation) -> None:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutation(value)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )


def test_catalog_is_deterministic_and_digest_pinned():
    first, manifests = catalog.build_catalog()
    second, _ = catalog.build_catalog()

    assert first == second
    assert first["catalog_version"] == 1
    assert first["templates_digest"] == catalog.sha256(
        catalog.canonical_bytes(first["templates"])
    )
    template = first["templates"][0]
    assert (
        template["publisher"],
        template["name"],
        template["version"],
        template["status"],
    ) == ("weynear", "sports-live-scores", "1.0.0", "preview")
    assert template["source"]["repository"] == (
        "https://github.com/ericel/wahalao-automation"
    )
    assert template["artifact"]["uri"].startswith(
        "us-central1-docker.pkg.dev/"
    )
    assert template["artifact"]["uri"].endswith(
        f"@{template['artifact']['digest']}"
    )
    manifest_path = template["install_manifest"]["path"]
    assert manifest_path in manifests
    assert template["install_manifest"]["digest"] == catalog.sha256(
        manifests[manifest_path].encode("utf-8")
    )


def test_checked_in_catalog_matches_builder():
    built, _ = catalog.build_catalog()
    assert catalog.CATALOG.read_text(encoding="utf-8") == (
        json.dumps(built, indent=2, sort_keys=True) + "\n"
    )


def test_release_contains_only_catalog_declared_manifests(tmp_path):
    built, manifests = catalog.build_catalog()
    release = tmp_path / "release"

    catalog.write_release(release, built, manifests)

    assert json.loads(release.joinpath("catalog.json").read_text()) == built
    assert release.joinpath("catalog-version.txt").read_text() == (
        f"{built['catalog_version']}\n"
    )
    released = {
        path.relative_to(release).as_posix()
        for path in release.rglob("*")
        if path.is_file()
        and path.name not in {"catalog.json", "catalog-version.txt"}
    }
    assert released == set(manifests)


def test_recipe_schema_rejects_unknown_fields(tmp_path, monkeypatch):
    _, recipe, _, _ = isolated_registry(tmp_path, monkeypatch)
    mutate_yaml(recipe, lambda value: value["spec"].update({"surprise": True}))

    with pytest.raises(ValueError, match="Additional properties"):
        catalog.build_catalog()


def test_source_repository_must_be_registered(tmp_path, monkeypatch):
    _, recipe, _, _ = isolated_registry(tmp_path, monkeypatch)
    mutate_yaml(
        recipe,
        lambda value: value["spec"]["source"].update(
            {"repository": "https://github.com/ericel/unregistered"}
        ),
    )

    with pytest.raises(ValueError, match="source repository is not registered"):
        catalog.build_catalog()


def test_source_commit_must_be_full_and_nonzero(tmp_path, monkeypatch):
    _, recipe, _, _ = isolated_registry(tmp_path, monkeypatch)
    mutate_yaml(
        recipe,
        lambda value: value["spec"]["source"].update({"commit": "0" * 40}),
    )

    with pytest.raises(ValueError, match="nonzero full Git SHA"):
        catalog.build_catalog()


def test_artifact_digest_must_match_uri(tmp_path, monkeypatch):
    _, recipe, _, _ = isolated_registry(tmp_path, monkeypatch)
    mutate_yaml(
        recipe,
        lambda value: value["spec"]["artifact"].update(
            {"digest": f"sha256:{'f' * 64}"}
        ),
    )

    with pytest.raises(ValueError, match="declared digest disagree"):
        catalog.build_catalog()


def test_artifact_must_stay_in_publisher_namespace(tmp_path, monkeypatch):
    _, recipe, _, _ = isolated_registry(tmp_path, monkeypatch)

    def escape(value):
        artifact = value["spec"]["artifact"]
        artifact["uri"] = artifact["uri"].replace(
            "/weynear/sports-live-scores@",
            "/attacker/sports-live-scores@",
        )

    mutate_yaml(recipe, escape)

    with pytest.raises(ValueError, match="outside the publisher namespace"):
        catalog.build_catalog()


def test_manifest_rejects_undeclared_placeholder(tmp_path, monkeypatch):
    _, _, manifest, _ = isolated_registry(tmp_path, monkeypatch)
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "${DISPLAY_NAME}",
            "${CONFIG:UNDECLARED}",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="undeclared configuration placeholder"):
        catalog.build_catalog()


def test_binding_must_name_a_compatible_destination(tmp_path, monkeypatch):
    _, recipe, _, _ = isolated_registry(tmp_path, monkeypatch)
    mutate_yaml(
        recipe,
        lambda value: value["spec"]["bindings"][0].update(
            {"manifest_destination": "missing-posts"}
        ),
    )

    with pytest.raises(ValueError, match="undeclared manifest destination"):
        catalog.build_catalog()


def test_publisher_repository_must_match_protected_owner(
    tmp_path,
    monkeypatch,
):
    _, _, _, publisher = isolated_registry(tmp_path, monkeypatch)
    mutate_yaml(
        publisher,
        lambda value: value["spec"]["github"]["repositories"].append(
            "https://github.com/attacker/template"
        ),
    )

    with pytest.raises(ValueError, match="outside the protected GitHub owner"):
        catalog.build_catalog()


def test_catalog_version_is_positive_integer(tmp_path, monkeypatch):
    registry, _, _, _ = isolated_registry(tmp_path, monkeypatch)
    registry.joinpath("catalog-version.txt").write_text("latest\n")

    with pytest.raises(ValueError, match="positive integer"):
        catalog.build_catalog()


def test_trusted_builder_can_promote_preview_recipe(tmp_path, monkeypatch):
    registry, recipe, _, _ = isolated_registry(tmp_path, monkeypatch)
    source_commit = "a" * 40
    artifact_digest = f"sha256:{'b' * 64}"

    promoted = promotion.promote(
        registry,
        publisher="weynear",
        name="sports-live-scores",
        version="1.0.0",
        source_commit=source_commit,
        artifact_digest=artifact_digest,
    )

    assert promoted == recipe
    document = yaml.safe_load(recipe.read_text(encoding="utf-8"))
    assert document["metadata"]["status"] == "approved"
    assert document["spec"]["source"]["commit"] == source_commit
    assert document["spec"]["artifact"]["digest"] == artifact_digest
    assert document["spec"]["artifact"]["uri"].endswith(
        f"@{artifact_digest}"
    )
    built, _ = catalog.build_catalog()
    assert built["templates"][0]["status"] == "approved"


def test_promotion_rejects_untrusted_digest_shape(tmp_path, monkeypatch):
    registry, _, _, _ = isolated_registry(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="invalid artifact digest"):
        promotion.promote(
            registry,
            publisher="weynear",
            name="sports-live-scores",
            version="1.0.0",
            source_commit="a" * 40,
            artifact_digest="latest",
        )


def test_immutability_check_maps_any_version_file_to_its_template():
    assert immutability.template_path_for(
        "registry/recipes/weynear/sports-live-scores/1.0.0/README.md"
    ) == (
        "registry/recipes/weynear/sports-live-scores/1.0.0/template.yaml"
    )


def test_immutability_check_ignores_non_recipe_paths():
    assert immutability.template_path_for("README.md") is None
    assert immutability.template_path_for(
        "registry/publishers/weynear.yaml"
    ) is None

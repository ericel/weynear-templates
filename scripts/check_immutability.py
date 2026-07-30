#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import PurePosixPath

import yaml


RECIPE_PREFIX = PurePosixPath("registry/recipes")
IMMUTABLE_STATUSES = {"approved", "deprecated"}


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def base_file(base: str, path: str) -> str | None:
    result = git("show", f"{base}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def template_path_for(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if len(parts) < 6 or PurePosixPath(*parts[:2]) != RECIPE_PREFIX:
        return None
    return PurePosixPath(*parts[:5], "template.yaml").as_posix()


def immutable_changed_versions(base: str) -> list[str]:
    changed = git(
        "diff",
        "--name-only",
        "--diff-filter=ACDMRT",
        f"{base}...HEAD",
        "--",
        "registry/recipes",
    ).stdout.splitlines()
    candidates = {
        template_path
        for path in changed
        if (template_path := template_path_for(path)) is not None
    }
    violations = []
    for template_path in sorted(candidates):
        previous = base_file(base, template_path)
        if previous is None:
            continue
        document = yaml.safe_load(previous)
        status = str(
            ((document or {}).get("metadata") or {}).get("status") or ""
        )
        if status in IMMUTABLE_STATUSES:
            violations.append(template_path.rsplit("/", 1)[0])
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", help="base commit SHA or ref")
    args = parser.parse_args()
    violations = immutable_changed_versions(args.base)
    if violations:
        joined = "\n".join(f"- {item}" for item in violations)
        raise SystemExit(
            "approved/deprecated template versions are immutable; "
            "publish a new semantic version:\n"
            f"{joined}"
        )
    print("immutable released template versions were not modified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

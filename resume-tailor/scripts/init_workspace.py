#!/usr/bin/env python3
"""Initialize an evidence-first resume workspace without overwriting user files."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


DIRECTORIES = (
    "inbox",
    "sources/extracted",
    "profile",
    "experiences",
    "projects",
    "jobs",
    "outputs",
    "state/staging",
    "state/templates",
)

EMPTY_JSON_FILES = {
    "sources/source-catalog.json": {"sources": []},
    "profile/education.json": {"education": []},
    "profile/skills.json": {"skills": []},
    "profile/awards.json": {"awards": []},
    "profile/preferences.json": {},
    "profile/pending-questions.json": {"questions": []},
}

EMPTY_TEXT_FILES = (
    "sources/ingestion-report.md",
    "profile/completeness-report.md",
)


def write_json_if_missing(path: Path, payload: object) -> bool:
    if path.is_file():
        return False
    if path.exists():
        raise IsADirectoryError(f"Expected a file but found another path type: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def copy_file_if_missing(source: Path, destination: Path) -> bool:
    if destination.is_file():
        return False
    if destination.exists():
        raise IsADirectoryError(f"Expected a file but found another path type: {destination}")
    shutil.copyfile(source, destination)
    return True


def initialize(root: Path) -> tuple[list[Path], list[Path]]:
    root = root.expanduser().resolve()
    created: list[Path] = []
    preserved: list[Path] = []

    for relative in DIRECTORIES:
        path = root / relative
        if path.is_dir():
            preserved.append(path)
        elif path.exists():
            raise NotADirectoryError(f"Expected a directory but found another path type: {path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    templates = Path(__file__).resolve().parent.parent / "assets" / "templates"
    for source in sorted(templates.glob("*.json")):
        destination = root / "state" / "templates" / source.name
        if copy_file_if_missing(source, destination):
            created.append(destination)
        else:
            preserved.append(destination)

    candidate_template = templates / "candidate-profile.json"
    candidate_path = root / "profile" / "candidate-profile.json"
    if copy_file_if_missing(candidate_template, candidate_path):
        created.append(candidate_path)
    else:
        preserved.append(candidate_path)

    run_template = templates / "run-manifest.json"
    run_path = root / "state" / "run-manifest.json"
    if copy_file_if_missing(run_template, run_path):
        created.append(run_path)
    else:
        preserved.append(run_path)

    for relative, payload in EMPTY_JSON_FILES.items():
        path = root / relative
        if write_json_if_missing(path, payload):
            created.append(path)
        else:
            preserved.append(path)

    for relative in EMPTY_TEXT_FILES:
        path = root / relative
        if path.is_file():
            preserved.append(path)
        elif path.exists():
            raise IsADirectoryError(f"Expected a file but found another path type: {path}")
        else:
            path.write_text("", encoding="utf-8")
            created.append(path)

    manifest_path = root / "state" / "workspace-manifest.json"
    if manifest_path.is_file():
        preserved.append(manifest_path)
    elif manifest_path.exists():
        raise IsADirectoryError(f"Expected a file but found another path type: {manifest_path}")
    else:
        manifest = {
            "schema_version": "1.1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workspace_root": str(root),
            "status": "initialized",
        }
        if write_json_if_missing(manifest_path, manifest):
            created.append(manifest_path)

    change_log = root / "state" / "change-log.jsonl"
    if change_log.is_file():
        preserved.append(change_log)
    elif change_log.exists():
        raise IsADirectoryError(f"Expected a file but found another path type: {change_log}")
    else:
        change_log.touch()
        created.append(change_log)

    return created, preserved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("workspace"), help="Workspace directory")
    args = parser.parse_args()
    try:
        created, preserved = initialize(args.root)
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Workspace: {args.root.expanduser().resolve()}")
    print(f"Created: {len(created)}")
    print(f"Preserved: {len(preserved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

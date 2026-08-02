#!/usr/bin/env python3
"""Stage, validate, and atomically apply job-analysis and evidence-matching artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_workspace import (
    EVIDENCE_STATUSES,
    ID_PATTERN,
    RECORD_TYPES,
    RESUME_RECOMMENDATIONS,
    RUN_MODES,
    RUN_STATUSES,
    validate,
)


BUNDLE_SCHEMA_VERSION = "match-bundle-1.0"
MATCH_STAGES = ("analyze-job", "match")
ANALYZE_STAGES = ("analyze-job",)
JSON_JOB_CONTRACTS = {
    "job-metadata.json": {
        "job_id": str,
        "company": str,
        "role": str,
        "location": str,
        "source_url": str,
        "user_version": bool,
        "web_verified": bool,
        "accessed_at": str,
        "target_language": str,
        "page_limit": int,
    },
    "jd-analysis.json": {
        "role_objective": list,
        "responsibilities": list,
        "must_have": list,
        "nice_to_have": list,
        "competencies": list,
        "keywords": list,
        "hard_constraints": list,
        "inferred_requirements": list,
        "priority_weights": list,
    },
    "evidence-matrix.json": {
        "job_id": str,
        "requirements": list,
        "record_ranking": list,
        "uncovered_requirements": list,
        "weak_evidence": list,
    },
}
TEXT_JOB_FILES = {"jd-original.md", "jd-analysis-summary.md"}
COMMON_BUNDLE_FILES = {
    "manifest.json",
    "jd-original.md",
    "job-metadata.json",
    "jd-analysis.json",
    "jd-analysis-summary.md",
}
SCORE_WEIGHTS = {
    "jd_relevance": 0.35,
    "evidence_strength": 0.25,
    "candidate_ownership": 0.15,
    "result_impact": 0.10,
    "differentiation": 0.10,
    "keyword_coverage": 0.05,
}
REQUIREMENT_KEYS = {
    "requirement",
    "priority",
    "matched_records",
    "evidence",
    "source_refs",
    "evidence_status",
    "score_breakdown",
    "resume_recommendation",
    "risk",
    "interview_follow_up",
}
RUN_MANIFEST_KEYS = {
    "task",
    "mode",
    "target_job_id",
    "available_inputs",
    "missing_inputs",
    "planned_stages",
    "completed_stages",
    "status",
    "limitations",
    "updated_at",
}
SOURCE_ID_PATTERN = re.compile(r"^src-[0-9]+$")


class BundleError(ValueError):
    """Raised when a bundle is unsafe or violates a workspace contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"{path.name}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise BundleError(f"{path.name}: expected a JSON object")
    return value


def require_contract(
    file_name: str,
    data: dict[str, Any],
    contract: dict[str, object],
) -> None:
    for key, expected_type in contract.items():
        if key not in data:
            raise BundleError(f"{file_name}.{key}: missing required field")
        if not isinstance(data[key], expected_type):
            raise BundleError(f"{file_name}.{key}: invalid type")


def ensure_job_id(file_name: str, data: dict[str, Any], job_id: str) -> None:
    existing = data.get("job_id")
    if existing is None and file_name == "jd-analysis.json":
        data["job_id"] = job_id
    elif existing != job_id:
        raise BundleError(f"{file_name}.job_id: expected {job_id!r}, got {existing!r}")


def record_path(root: Path, record_type: str, record_id: str) -> Path:
    directory = "projects" if record_type == "project" else "experiences"
    return root / directory / f"{record_id}.json"


def calculate_score(score_breakdown: dict[str, Any], path: str) -> int:
    missing = set(SCORE_WEIGHTS) - score_breakdown.keys()
    if missing:
        raise BundleError(f"{path}: missing score fields: {', '.join(sorted(missing))}")
    weighted = 0.0
    for field, weight in SCORE_WEIGHTS.items():
        value = score_breakdown[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BundleError(f"{path}.{field}: expected a number from 0 to 100")
        if not 0 <= value <= 100:
            raise BundleError(f"{path}.{field}: score must be between 0 and 100")
        weighted += float(value) * weight
    return int(weighted + 0.5)


def normalize_evidence_matrix(root: Path, data: dict[str, Any], job_id: str) -> int:
    require_contract("evidence-matrix.json", data, JSON_JOB_CONTRACTS["evidence-matrix.json"])
    ensure_job_id("evidence-matrix.json", data, job_id)
    normalized_scores = 0
    for index, requirement in enumerate(data["requirements"]):
        path = f"evidence-matrix.json.requirements[{index}]"
        if not isinstance(requirement, dict):
            raise BundleError(f"{path}: expected an object")
        missing = REQUIREMENT_KEYS - requirement.keys()
        if missing:
            raise BundleError(f"{path}: missing fields: {', '.join(sorted(missing))}")
        if requirement["evidence_status"] not in EVIDENCE_STATUSES:
            allowed = ", ".join(sorted(EVIDENCE_STATUSES))
            raise BundleError(
                f"{path}.evidence_status: invalid value {requirement['evidence_status']!r}; "
                f"allowed: {allowed}"
            )
        if requirement["resume_recommendation"] not in RESUME_RECOMMENDATIONS:
            allowed = ", ".join(sorted(RESUME_RECOMMENDATIONS))
            raise BundleError(
                f"{path}.resume_recommendation: invalid value "
                f"{requirement['resume_recommendation']!r}; allowed: {allowed}"
            )
        for list_field in (
            "matched_records",
            "evidence",
            "source_refs",
            "interview_follow_up",
        ):
            if not isinstance(requirement[list_field], list):
                raise BundleError(f"{path}.{list_field}: expected an array")
        if isinstance(requirement["priority"], bool) or not isinstance(
            requirement["priority"], (int, float)
        ):
            raise BundleError(f"{path}.priority: expected a number")
        if not isinstance(requirement["score_breakdown"], dict):
            raise BundleError(f"{path}.score_breakdown: expected an object")

        seen_records: set[tuple[str, str]] = set()
        for record_index, record in enumerate(requirement["matched_records"]):
            record_field = f"{path}.matched_records[{record_index}]"
            if not isinstance(record, dict):
                raise BundleError(f"{record_field}: expected an object")
            record_type = record.get("record_type")
            record_id = record.get("record_id")
            if record_type not in RECORD_TYPES:
                raise BundleError(f"{record_field}.record_type: invalid value {record_type!r}")
            if not isinstance(record_id, str) or not ID_PATTERN.fullmatch(record_id):
                raise BundleError(f"{record_field}.record_id: invalid identifier {record_id!r}")
            if not record_path(root, record_type, record_id).is_file():
                raise BundleError(
                    f"{record_field}: referenced {record_type} does not exist: {record_id}"
                )
            identity = (record_type, record_id)
            if identity in seen_records:
                raise BundleError(f"{record_field}: duplicate record reference")
            seen_records.add(identity)

        calculated = calculate_score(requirement["score_breakdown"], f"{path}.score_breakdown")
        if requirement.get("match_score") != calculated:
            normalized_scores += 1
        requirement["match_score"] = calculated
    return normalized_scores


def validate_job_artifacts(
    root: Path,
    bundle_dir: Path,
    job_id: str,
) -> tuple[dict[str, bytes], int]:
    updates: dict[str, bytes] = {}
    normalized_scores = 0
    for file_name, contract in JSON_JOB_CONTRACTS.items():
        if not (bundle_dir / file_name).is_file():
            continue
        data = load_json(bundle_dir / file_name)
        if file_name == "evidence-matrix.json":
            normalized_scores += normalize_evidence_matrix(root, data, job_id)
        else:
            ensure_job_id(file_name, data, job_id)
            require_contract(file_name, data, contract)
        updates[file_name] = (
            json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")

    for file_name in TEXT_JOB_FILES:
        text = (bundle_dir / file_name).read_text(encoding="utf-8")
        if not text.strip():
            raise BundleError(f"{file_name}: file must not be empty")
        updates[file_name] = text.encode("utf-8")
    return updates, normalized_scores


def validate_source_upserts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    values = manifest.get("source_catalog_upserts", [])
    if not isinstance(values, list):
        raise BundleError("manifest.json.source_catalog_upserts: expected an array")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        path = f"manifest.json.source_catalog_upserts[{index}]"
        if not isinstance(value, dict):
            raise BundleError(f"{path}: expected an object")
        source_id = value.get("source_id")
        if not isinstance(source_id, str) or not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise BundleError(f"{path}.source_id: invalid source identifier {source_id!r}")
        if source_id in seen:
            raise BundleError(f"{path}.source_id: duplicate source identifier")
        seen.add(source_id)
        result.append(value)
    return result


def merge_source_catalog(root: Path, upserts: list[dict[str, Any]]) -> bytes:
    path = root / "sources/source-catalog.json"
    catalog = load_json(path)
    sources = catalog.get("sources")
    if not isinstance(sources, list):
        raise BundleError("sources/source-catalog.json.sources: expected an array")
    positions = {
        source.get("source_id"): index
        for index, source in enumerate(sources)
        if isinstance(source, dict) and isinstance(source.get("source_id"), str)
    }
    for upsert in upserts:
        source_id = upsert["source_id"]
        if source_id in positions:
            current = sources[positions[source_id]]
            if not isinstance(current, dict):
                raise BundleError(f"source catalog item for {source_id} is not an object")
            merged = dict(current)
            merged.update(upsert)
            sources[positions[source_id]] = merged
        else:
            positions[source_id] = len(sources)
            sources.append(upsert)
    return (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def merge_run_manifest(
    root: Path,
    manifest: dict[str, Any],
    job_id: str,
    mode: str,
) -> bytes:
    patch = manifest.get("run_manifest_patch", {})
    if not isinstance(patch, dict):
        raise BundleError("manifest.json.run_manifest_patch: expected an object")
    required_patch = {
        "available_inputs",
        "missing_inputs",
        "planned_stages",
        "completed_stages",
        "status",
        "limitations",
    }
    missing_patch = required_patch - patch.keys()
    if missing_patch:
        raise BundleError(
            "manifest.json.run_manifest_patch: missing fields: "
            + ", ".join(sorted(missing_patch))
        )
    unknown = patch.keys() - RUN_MANIFEST_KEYS
    if unknown:
        raise BundleError(
            "manifest.json.run_manifest_patch: unknown fields: " + ", ".join(sorted(unknown))
        )
    current = load_json(root / "state/run-manifest.json")
    current.update(patch)
    stages = MATCH_STAGES if mode == "match" else ANALYZE_STAGES
    current["mode"] = mode
    current["target_job_id"] = job_id
    current.setdefault("task", f"Analyze and match job {job_id}")
    current.setdefault("available_inputs", [])
    current.setdefault("missing_inputs", [])
    current.setdefault("planned_stages", list(stages))
    current.setdefault("completed_stages", list(stages))
    current.setdefault("status", "complete")
    current.setdefault("limitations", [])
    current["updated_at"] = patch.get("updated_at") or utc_now()

    for key in (
        "task",
        "mode",
        "available_inputs",
        "missing_inputs",
        "planned_stages",
        "completed_stages",
        "status",
        "limitations",
        "updated_at",
    ):
        if key not in current:
            raise BundleError(f"state/run-manifest.json.{key}: missing required field")
    if current["mode"] not in RUN_MODES:
        raise BundleError("state/run-manifest.json.mode: invalid run mode")
    if current["status"] not in RUN_STATUSES:
        raise BundleError("state/run-manifest.json.status: invalid run status")
    for key in (
        "available_inputs",
        "missing_inputs",
        "planned_stages",
        "completed_stages",
        "limitations",
    ):
        if not isinstance(current[key], list):
            raise BundleError(f"state/run-manifest.json.{key}: expected an array")
    return (json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def merge_change_log(root: Path, manifest: dict[str, Any]) -> bytes:
    entries = manifest.get("change_log_entries", [])
    if not isinstance(entries, list):
        raise BundleError("manifest.json.change_log_entries: expected an array")
    path = root / "state/change-log.jsonl"
    existing_lines = path.read_text(encoding="utf-8").splitlines()
    canonical_existing: set[str] = set()
    for line_number, line in enumerate(existing_lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BundleError(f"state/change-log.jsonl:{line_number}: invalid JSON: {exc}") from exc
        canonical_existing.add(json.dumps(value, ensure_ascii=False, sort_keys=True))

    output_lines = [line for line in existing_lines if line.strip()]
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise BundleError(f"manifest.json.change_log_entries[{index}]: expected an object")
        canonical = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        if canonical not in canonical_existing:
            output_lines.append(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
            canonical_existing.add(canonical)
    text = "\n".join(output_lines)
    if text:
        text += "\n"
    return text.encode("utf-8")


def ensure_bundle_directory(root: Path, bundle_dir: Path) -> Path:
    root = root.expanduser().resolve()
    bundle_dir = bundle_dir.expanduser().resolve()
    staging_root = (root / "state/staging").resolve()
    try:
        bundle_dir.relative_to(staging_root)
    except ValueError as exc:
        raise BundleError(f"Bundle must be inside {staging_root}") from exc
    if bundle_dir == staging_root or not bundle_dir.is_dir():
        raise BundleError(f"Bundle directory does not exist: {bundle_dir}")
    return bundle_dir


def check_required_bundle_files(bundle_dir: Path, mode: str) -> None:
    required = set(COMMON_BUNDLE_FILES)
    if mode == "match":
        required.add("evidence-matrix.json")
    missing = sorted(name for name in required if not (bundle_dir / name).is_file())
    if missing:
        raise BundleError("Bundle is missing required files: " + ", ".join(missing))


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def restore_files(backups: dict[Path, bytes | None]) -> None:
    for path, content in backups.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            write_atomic(path, content)


def apply_bundle(
    root: Path,
    bundle_dir: Path,
    consume: bool,
    dry_run: bool,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    bundle_dir = ensure_bundle_directory(root, bundle_dir)

    pre_errors, _ = validate(root)
    if pre_errors:
        raise BundleError("Workspace is invalid before apply: " + "; ".join(pre_errors[:8]))

    manifest = load_json(bundle_dir / "manifest.json")
    if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise BundleError(
            f"manifest.json.schema_version: expected {BUNDLE_SCHEMA_VERSION!r}"
        )
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not ID_PATTERN.fullmatch(job_id):
        raise BundleError(f"manifest.json.job_id: invalid identifier {job_id!r}")

    mode = manifest.get("mode", "match")
    if mode not in {"analyze-job", "match"}:
        raise BundleError(f"manifest.json.mode: invalid value {mode!r}")
    check_required_bundle_files(bundle_dir, mode)

    job_updates, normalized_scores = validate_job_artifacts(root, bundle_dir, job_id)
    source_upserts = validate_source_upserts(manifest)
    updates: dict[Path, bytes] = {
        root / "jobs" / job_id / file_name: content
        for file_name, content in job_updates.items()
    }
    updates[root / "sources/source-catalog.json"] = merge_source_catalog(root, source_upserts)
    updates[root / "state/run-manifest.json"] = merge_run_manifest(
        root,
        manifest,
        job_id,
        mode,
    )
    updates[root / "state/change-log.jsonl"] = merge_change_log(root, manifest)

    changed = [
        str(path.relative_to(root))
        for path, content in updates.items()
        if not path.is_file() or path.read_bytes() != content
    ]
    preserved = [
        str(path.relative_to(root))
        for path, content in updates.items()
        if path.is_file() and path.read_bytes() == content
    ]
    if dry_run:
        return {
            "status": "valid",
            "job_id": job_id,
            "changed": changed,
            "preserved": preserved,
            "normalized_scores": normalized_scores,
            "bundle_consumed": False,
        }

    backups = {path: path.read_bytes() if path.is_file() else None for path in updates}
    try:
        for path, content in updates.items():
            if backups[path] != content:
                write_atomic(path, content)
        post_errors, _ = validate(root)
        if post_errors:
            raise BundleError("Workspace validation failed after apply: " + "; ".join(post_errors[:8]))
    except BaseException:
        restore_files(backups)
        raise

    consumed = False
    cleanup_error: str | None = None
    if consume:
        try:
            shutil.rmtree(bundle_dir)
            consumed = True
        except OSError as exc:
            cleanup_error = str(exc)
    result = {
        "status": "applied",
        "job_id": job_id,
        "changed": changed,
        "preserved": preserved,
        "normalized_scores": normalized_scores,
        "bundle_consumed": consumed,
    }
    if cleanup_error:
        result["cleanup_error"] = cleanup_error
    return result


def start_run(root: Path, job_id: str, task: str, mode: str) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not ID_PATTERN.fullmatch(job_id):
        raise BundleError(f"Invalid job_id: {job_id!r}")
    errors, _ = validate(root)
    if errors:
        raise BundleError("Workspace validation failed: " + "; ".join(errors[:8]))

    staging_root = root / "state/staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    bundle_dir = Path(tempfile.mkdtemp(prefix=f"{job_id}-", dir=staging_root))
    stages = MATCH_STAGES if mode == "match" else ANALYZE_STAGES
    manifest_path = root / "state/run-manifest.json"
    run_manifest = load_json(manifest_path)
    run_manifest.update(
        {
            "task": task,
            "mode": mode,
            "target_job_id": job_id,
            "available_inputs": [],
            "missing_inputs": [],
            "planned_stages": list(stages),
            "completed_stages": [],
            "status": "in_progress",
            "limitations": [],
            "updated_at": utc_now(),
        }
    )
    write_atomic(
        manifest_path,
        (json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return {
        "status": "started",
        "job_id": job_id,
        "mode": mode,
        "bundle_dir": str(bundle_dir),
        "planned_stages": list(stages),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser(
        "start",
        help="Mark a match run in progress and create a collision-free staging directory",
    )
    start_parser.add_argument("--root", type=Path, default=Path("workspace"))
    start_parser.add_argument("--job-id", required=True)
    start_parser.add_argument("--task", required=True)
    start_parser.add_argument(
        "--mode",
        choices=("analyze-job", "match"),
        default="match",
    )

    apply_parser = subparsers.add_parser(
        "apply",
        help="Validate and apply a staged match bundle without line-based patches",
    )
    apply_parser.add_argument("--root", type=Path, default=Path("workspace"))
    apply_parser.add_argument("--bundle-dir", type=Path, required=True)
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument(
        "--consume",
        action="store_true",
        help="Remove the generated staging directory after a successful apply",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "start":
            result = start_run(args.root, args.job_id, args.task, args.mode)
        else:
            result = apply_bundle(args.root, args.bundle_dir, args.consume, args.dry_run)
    except (BundleError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

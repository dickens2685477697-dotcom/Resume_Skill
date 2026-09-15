#!/usr/bin/env python3
"""Validate resume workspace structure and JSON contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


REQUIRED_DIRECTORIES = (
    "inbox",
    "sources",
    "sources/extracted",
    "profile",
    "experiences",
    "projects",
    "jobs",
    "outputs",
    "state",
    "state/templates",
)

CORE_JSON_CONTRACTS = {
    "sources/source-catalog.json": {"sources": list},
    "profile/candidate-profile.json": {
        "name": str,
        "headline": str,
        "contact": dict,
        "summary_evidence": list,
        "source_refs": list,
        "field_evidence": dict,
        "updated_at": str,
    },
    "profile/education.json": {"education": list},
    "profile/skills.json": {"skills": list},
    "profile/awards.json": {"awards": list},
    "profile/preferences.json": {},
    "profile/pending-questions.json": {"questions": list},
    "state/workspace-manifest.json": {
        "schema_version": str,
        "created_at": str,
        "workspace_root": str,
        "status": str,
    },
    "state/run-manifest.json": {
        "task": str,
        "mode": str,
        "target_job_id": (str, type(None)),
        "available_inputs": list,
        "missing_inputs": list,
        "planned_stages": list,
        "completed_stages": list,
        "status": str,
        "limitations": list,
        "updated_at": str,
    },
}

REQUIRED_TEXT_FILES = (
    "sources/ingestion-report.md",
    "profile/completeness-report.md",
    "state/change-log.jsonl",
)

COMMON_RECORD_KEYS = {
    "experience_type",
    "actions",
    "deliverables",
    "results",
    "source_refs",
    "field_evidence",
    "star_completeness",
    "status",
}

RECORD_IDENTITIES = {
    "projects": ("project_id", "project_name"),
    "experiences": ("experience_id", "experience_name"),
}

RECORD_LIST_FIELDS = {
    "background",
    "business_goal",
    "user_problem",
    "task",
    "actions",
    "deliverables",
    "results",
    "metrics",
    "decisions",
    "tradeoffs",
    "collaboration",
    "skills",
    "tools",
    "source_refs",
}

EVIDENCE_STATUSES = {
    "verified",
    "user_confirmed",
    "inferred",
    "conflicting",
    "missing",
    "missing_confirmed",
    "unsupported",
}

RECORD_STATUSES = {"draft", "complete", "usable_with_gaps", "insufficient"}
EXPERIENCE_TYPES = {"internship", "employment", "research", "course", "personal", "volunteer"}
MEASUREMENT_TYPES = {"actual", "target", "baseline", "estimate"}
RUN_MODES = {"initialize", "ingest", "validate", "analyze-job", "match", "polish", "generate", "audit", "update", "full-run"}
RUN_STATUSES = {"in_progress", "needs_confirmation", "complete", "partial"}
RECORD_TYPES = {"project", "experience"}
RESUME_RECOMMENDATIONS = {"include", "supporting", "exclude", "confirm"}
OWNERSHIP_TYPES = {"individual", "shared", "team_result"}
BULLET_SELECTION_STATUSES = {"selected", "alternate", "exclude"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid JSON: {path}: {exc}")
        return None


def validate_contract(path: Path, data: object, contract: dict[str, object], errors: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append(f"Expected JSON object: {path}")
        return
    for key, expected_type in contract.items():
        if key not in data:
            errors.append(f"Missing key {key!r}: {path}")
        elif not isinstance(data[key], expected_type):
            errors.append(f"Invalid type for {key!r}: {path}")


def validate_identifier(value: object, label: str, path: Path, errors: list[str]) -> None:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        errors.append(f"Invalid {label} {value!r}: {path}")


def validate_record_reference(root: Path, record_type: object, record_id: object, path: Path, errors: list[str]) -> None:
    if record_type not in RECORD_TYPES or not isinstance(record_id, str) or not ID_PATTERN.fullmatch(record_id):
        return
    directory = "projects" if record_type == "project" else "experiences"
    if not (root / directory / f"{record_id}.json").is_file():
        errors.append(f"Referenced {record_type} record does not exist: {record_id!r}: {path}")


def validate_field_evidence(value: object, path: Path, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"field_evidence must be an object: {path}")
        return
    for field, evidence in value.items():
        if not isinstance(evidence, dict):
            errors.append(f"Evidence for {field} must be an object: {path}")
            continue
        status = evidence.get("status")
        if status not in EVIDENCE_STATUSES:
            errors.append(f"Invalid evidence status {status!r} for {field}: {path}")
        if "source_refs" in evidence and not isinstance(evidence["source_refs"], list):
            errors.append(f"source_refs for {field} must be an array: {path}")


def validate_record(path: Path, directory_name: str, errors: list[str], warnings: list[str]) -> None:
    data = load_json(path, errors)
    if not isinstance(data, dict):
        if data is not None:
            errors.append(f"Expected JSON object: {path}")
        return

    id_key, name_key = RECORD_IDENTITIES[directory_name]
    missing = sorted((COMMON_RECORD_KEYS | {id_key, name_key}) - data.keys())
    if missing:
        errors.append(f"Missing keys in {path}: {', '.join(missing)}")

    record_id = data.get(id_key)
    validate_identifier(record_id, id_key, path, errors)
    if isinstance(record_id, str) and path.stem != record_id:
        errors.append(f"File name must match {id_key} {record_id!r}: {path}")
    if not isinstance(data.get(name_key), str) or not data.get(name_key):
        errors.append(f"{name_key} must be a non-empty string: {path}")

    experience_type = data.get("experience_type")
    if experience_type not in EXPERIENCE_TYPES:
        errors.append(f"Invalid experience_type {experience_type!r}: {path}")
    if data.get("status") not in RECORD_STATUSES:
        errors.append(f"Invalid record status {data.get('status')!r}: {path}")

    for field in RECORD_LIST_FIELDS:
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be an array: {path}")

    validate_field_evidence(data.get("field_evidence"), path, errors)

    star = data.get("star_completeness")
    if not isinstance(star, dict):
        errors.append(f"star_completeness must be an object: {path}")
    else:
        for field in ("situation", "task", "action", "result"):
            if star.get(field) not in EVIDENCE_STATUSES:
                errors.append(f"Invalid STAR status for {field}: {path}")

    metrics = data.get("metrics", [])
    if isinstance(metrics, list):
        for index, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                errors.append(f"metrics[{index}] must be an object: {path}")
                continue
            if metric.get("measurement_type") not in MEASUREMENT_TYPES:
                errors.append(f"Invalid measurement_type in metrics[{index}]: {path}")
            if metric.get("evidence_status") not in EVIDENCE_STATUSES:
                errors.append(f"Invalid evidence_status in metrics[{index}]: {path}")

    if data.get("status") == "complete" and not data.get("actions"):
        warnings.append(f"Complete record has no actions: {path}")


def validate_change_log(path: Path, errors: list[str]) -> None:
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                errors.append(f"Change-log entry must be an object at line {line_number}: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid JSONL: {path}: {exc}")


def validate_job_files(root: Path, errors: list[str]) -> None:
    contracts = {
        "job-metadata.json": {"job_id": str, "company": str, "role": str, "location": str, "source_url": str, "user_version": bool, "web_verified": bool, "accessed_at": str, "target_language": str, "page_limit": int},
        "jd-analysis.json": {"role_objective": list, "responsibilities": list, "must_have": list, "nice_to_have": list, "competencies": list, "keywords": list, "hard_constraints": list, "inferred_requirements": list, "priority_weights": list},
        "evidence-matrix.json": {"job_id": str, "requirements": list, "record_ranking": list, "uncovered_requirements": list, "weak_evidence": list},
        "experience-tailoring.json": {"job_id": str, "source_evidence_matrix_sha256": str, "role_narrative": dict, "records": list, "cross_record_strategy": dict, "unresolved_questions": list, "updated_at": str},
        "resume-plan.json": {"target_language": str, "page_limit": int, "selected_experiences": list, "selected_projects": list, "bullet_plan": list, "section_order": list, "excluded_items": list, "coverage_summary": dict, "known_gaps": list},
    }
    jobs = root / "jobs"
    if not jobs.is_dir():
        return
    for job_dir in sorted(path for path in jobs.iterdir() if path.is_dir()):
        validate_identifier(job_dir.name, "job_id", job_dir, errors)
        for file_name, contract in contracts.items():
            path = job_dir / file_name
            if path.exists():
                data = load_json(path, errors)
                if data is not None:
                    validate_contract(path, data, contract, errors)
                if isinstance(data, dict) and "job_id" in data:
                    validate_identifier(data["job_id"], "job_id", path, errors)
                    if data["job_id"] != job_dir.name:
                        errors.append(f"job_id must match directory name {job_dir.name!r}: {path}")
                if file_name == "evidence-matrix.json" and isinstance(data, dict) and isinstance(data.get("requirements"), list):
                    for index, requirement in enumerate(data["requirements"]):
                        if not isinstance(requirement, dict):
                            errors.append(f"requirements[{index}] must be an object: {path}")
                            continue
                        missing = {"requirement", "priority", "matched_records", "evidence", "source_refs", "evidence_status", "score_breakdown", "match_score", "resume_recommendation", "risk", "interview_follow_up"} - requirement.keys()
                        if missing:
                            errors.append(f"Missing keys in requirements[{index}]: {', '.join(sorted(missing))}: {path}")
                        if requirement.get("evidence_status") not in EVIDENCE_STATUSES:
                            errors.append(f"Invalid evidence_status in requirements[{index}]: {path}")
                        if requirement.get("resume_recommendation") not in RESUME_RECOMMENDATIONS:
                            errors.append(f"Invalid resume_recommendation in requirements[{index}]: {path}")
                        matched_records = requirement.get("matched_records")
                        if not isinstance(matched_records, list):
                            errors.append(f"matched_records in requirements[{index}] must be an array: {path}")
                            continue
                        for record_index, record in enumerate(matched_records):
                            if not isinstance(record, dict) or record.get("record_type") not in RECORD_TYPES:
                                errors.append(f"Invalid matched_records[{record_index}] in requirements[{index}]: {path}")
                                continue
                            validate_identifier(record.get("record_id"), "record_id", path, errors)
                            validate_record_reference(root, record.get("record_type"), record.get("record_id"), path, errors)
                if file_name == "experience-tailoring.json" and isinstance(data, dict) and isinstance(data.get("records"), list):
                    matrix_sha256 = data.get("source_evidence_matrix_sha256")
                    if not isinstance(matrix_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", matrix_sha256):
                        errors.append(f"Invalid source_evidence_matrix_sha256: {path}")
                    matrix_path = job_dir / "evidence-matrix.json"
                    if not matrix_path.is_file():
                        errors.append(f"experience-tailoring.json requires evidence-matrix.json: {path}")
                    elif isinstance(matrix_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", matrix_sha256):
                        actual_sha256 = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
                        if matrix_sha256 != actual_sha256:
                            errors.append(f"experience-tailoring.json is stale for evidence-matrix.json: {path}")
                    role_narrative = data.get("role_narrative")
                    if isinstance(role_narrative, dict):
                        missing = {"core_problem", "priority_signals", "expected_outputs", "supported_keywords", "unsafe_terms"} - role_narrative.keys()
                        if missing:
                            errors.append(f"Missing role_narrative keys: {', '.join(sorted(missing))}: {path}")
                    strategy = data.get("cross_record_strategy")
                    if isinstance(strategy, dict):
                        missing = {"primary_narrative", "coverage_allocation", "deduplication_decisions"} - strategy.keys()
                        if missing:
                            errors.append(f"Missing cross_record_strategy keys: {', '.join(sorted(missing))}: {path}")
                    for record_index, record in enumerate(data["records"]):
                        if not isinstance(record, dict):
                            errors.append(f"records[{record_index}] must be an object: {path}")
                            continue
                        required = {"record_type", "record_id", "positioning", "requirement_refs", "primary_signals", "supporting_signals", "evidence_selection", "bullet_candidates", "excluded_evidence"}
                        missing = required - record.keys()
                        if missing:
                            errors.append(f"Missing keys in records[{record_index}]: {', '.join(sorted(missing))}: {path}")
                        if record.get("record_type") not in RECORD_TYPES:
                            errors.append(f"Invalid record_type in records[{record_index}]: {path}")
                        validate_identifier(record.get("record_id"), "record_id", path, errors)
                        validate_record_reference(root, record.get("record_type"), record.get("record_id"), path, errors)
                        selections = record.get("evidence_selection")
                        if not isinstance(selections, list):
                            errors.append(f"evidence_selection in records[{record_index}] must be an array: {path}")
                        else:
                            for selection_index, selection in enumerate(selections):
                                if not isinstance(selection, dict):
                                    errors.append(f"evidence_selection[{selection_index}] in records[{record_index}] must be an object: {path}")
                                    continue
                                required_selection = {"field_paths", "source_refs", "evidence_status", "intended_signal", "ownership", "measurement_type"}
                                missing = required_selection - selection.keys()
                                if missing:
                                    errors.append(f"Missing keys in evidence_selection[{selection_index}] in records[{record_index}]: {', '.join(sorted(missing))}: {path}")
                                if selection.get("evidence_status") not in EVIDENCE_STATUSES:
                                    errors.append(f"Invalid evidence_status in evidence_selection[{selection_index}] in records[{record_index}]: {path}")
                                elif selection.get("evidence_status") not in {"verified", "user_confirmed"}:
                                    errors.append(f"Unusable evidence_status in evidence_selection[{selection_index}] in records[{record_index}]: {path}")
                                if selection.get("ownership") not in OWNERSHIP_TYPES:
                                    errors.append(f"Invalid ownership in evidence_selection[{selection_index}] in records[{record_index}]: {path}")
                                if not isinstance(selection.get("field_paths"), list) or not selection.get("field_paths"):
                                    errors.append(f"evidence_selection[{selection_index}] in records[{record_index}] must cite field_paths: {path}")
                                if not isinstance(selection.get("source_refs"), list) or not selection.get("source_refs"):
                                    errors.append(f"evidence_selection[{selection_index}] in records[{record_index}] must cite source_refs: {path}")
                                measurement_type = selection.get("measurement_type")
                                if measurement_type is not None and measurement_type not in MEASUREMENT_TYPES:
                                    errors.append(f"Invalid measurement_type in evidence_selection[{selection_index}] in records[{record_index}]: {path}")
                        bullets = record.get("bullet_candidates")
                        if not isinstance(bullets, list):
                            errors.append(f"bullet_candidates in records[{record_index}] must be an array: {path}")
                            continue
                        for bullet_index, bullet in enumerate(bullets):
                            if not isinstance(bullet, dict):
                                errors.append(f"bullet_candidates[{bullet_index}] in records[{record_index}] must be an object: {path}")
                                continue
                            required_bullet = {"bullet_id", "draft", "primary_signal", "requirement_refs", "field_paths", "source_refs", "evidence_status", "keyword_alignment", "ownership", "risk_notes", "selection_status"}
                            missing = required_bullet - bullet.keys()
                            if missing:
                                errors.append(f"Missing keys in bullet_candidates[{bullet_index}] in records[{record_index}]: {', '.join(sorted(missing))}: {path}")
                            validate_identifier(bullet.get("bullet_id"), "bullet_id", path, errors)
                            if bullet.get("evidence_status") not in EVIDENCE_STATUSES:
                                errors.append(f"Invalid evidence_status in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")
                            if bullet.get("ownership") not in OWNERSHIP_TYPES:
                                errors.append(f"Invalid ownership in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")
                            if bullet.get("selection_status") not in BULLET_SELECTION_STATUSES:
                                errors.append(f"Invalid selection_status in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")
                            if bullet.get("selection_status") == "selected" and bullet.get("evidence_status") not in {"verified", "user_confirmed"}:
                                errors.append(f"Selected bullet has unusable evidence_status in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")
                            if bullet.get("selection_status") in {"selected", "alternate"} and (not isinstance(bullet.get("field_paths"), list) or not bullet.get("field_paths")):
                                errors.append(f"Usable bullet must cite field_paths in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")
                            if bullet.get("selection_status") in {"selected", "alternate"} and (not isinstance(bullet.get("source_refs"), list) or not bullet.get("source_refs")):
                                errors.append(f"Usable bullet must cite source_refs in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")
                            if bullet.get("selection_status") in {"selected", "alternate"} and (not isinstance(bullet.get("requirement_refs"), list) or not bullet.get("requirement_refs")):
                                errors.append(f"Usable bullet must cite requirement_refs in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")
                            if bullet.get("selection_status") in {"selected", "alternate"} and not bullet.get("primary_signal"):
                                errors.append(f"Usable bullet must define primary_signal in bullet_candidates[{bullet_index}] in records[{record_index}]: {path}")


def validate_output_files(root: Path, errors: list[str]) -> None:
    outputs = root / "outputs"
    if not outputs.is_dir():
        return
    for job_dir in sorted(path for path in outputs.iterdir() if path.is_dir()):
        validate_identifier(job_dir.name, "job_id", job_dir, errors)
        source_map = job_dir / "resume-source-map.json"
        if not source_map.exists():
            continue
        data = load_json(source_map, errors)
        if data is None:
            continue
        validate_contract(source_map, data, {"job_id": str, "claims": list}, errors)
        if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
            continue
        validate_identifier(data.get("job_id"), "job_id", source_map, errors)
        if data.get("job_id") != job_dir.name:
            errors.append(f"job_id must match directory name {job_dir.name!r}: {source_map}")
        for index, claim in enumerate(data["claims"]):
            if not isinstance(claim, dict):
                errors.append(f"claims[{index}] must be an object: {source_map}")
                continue
            missing = {"claim_id", "text", "record_type", "record_id", "field_paths", "source_refs", "evidence_status"} - claim.keys()
            if missing:
                errors.append(f"Missing keys in claims[{index}]: {', '.join(sorted(missing))}: {source_map}")
            if claim.get("record_type") not in RECORD_TYPES:
                errors.append(f"Invalid record_type in claims[{index}]: {source_map}")
            validate_identifier(claim.get("record_id"), "record_id", source_map, errors)
            validate_record_reference(root, claim.get("record_type"), claim.get("record_id"), source_map, errors)
            if claim.get("evidence_status") not in EVIDENCE_STATUSES:
                errors.append(f"Invalid evidence_status in claims[{index}]: {source_map}")


def validate(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    root = root.expanduser().resolve()

    for relative in REQUIRED_DIRECTORIES:
        if not (root / relative).is_dir():
            errors.append(f"Missing directory: {relative}")

    loaded_core: dict[str, object] = {}
    for relative, contract in CORE_JSON_CONTRACTS.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing file: {relative}")
            continue
        data = load_json(path, errors)
        if data is not None:
            loaded_core[relative] = data
            validate_contract(path, data, contract, errors)

    run_manifest = loaded_core.get("state/run-manifest.json")
    if isinstance(run_manifest, dict):
        if run_manifest.get("mode") not in RUN_MODES:
            errors.append(f"Invalid run mode: {root / 'state/run-manifest.json'}")
        if run_manifest.get("status") not in RUN_STATUSES:
            errors.append(f"Invalid run status: {root / 'state/run-manifest.json'}")

    workspace_manifest = loaded_core.get("state/workspace-manifest.json")
    if isinstance(workspace_manifest, dict):
        if workspace_manifest.get("schema_version") != "1.1":
            errors.append(f"Unsupported schema_version: {root / 'state/workspace-manifest.json'}")
        if workspace_manifest.get("workspace_root") != str(root):
            errors.append(f"workspace_root does not match validated path: {root / 'state/workspace-manifest.json'}")

    for relative in REQUIRED_TEXT_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing file: {relative}")
    change_log = root / "state/change-log.jsonl"
    if change_log.is_file():
        validate_change_log(change_log, errors)

    asset_templates = Path(__file__).resolve().parent.parent / "assets/templates"
    for source in sorted(asset_templates.glob("*.json")):
        destination = root / "state/templates" / source.name
        if not destination.is_file():
            errors.append(f"Missing workspace template: state/templates/{source.name}")
        else:
            load_json(destination, errors)

    for directory_name in RECORD_IDENTITIES:
        directory = root / directory_name
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            validate_record(path, directory_name, errors, warnings)

    validate_job_files(root, errors)
    validate_output_files(root, errors)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("workspace"), help="Workspace directory")
    args = parser.parse_args()
    errors, warnings = validate(args.root)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"Validation failed: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"Validation passed: {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a bounded, evidence-aware context for resume-to-job matching."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from validate_workspace import validate


CARD_FIELDS = {
    "background": 1,
    "business_goal": 1,
    "user_problem": 1,
    "task": 1,
    "actions": 3,
    "deliverables": 2,
    "results": 2,
    "decisions": 2,
    "tradeoffs": 1,
    "collaboration": 2,
    "skills": 8,
    "tools": 8,
}
DETAIL_FIELDS = (
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
    "field_evidence",
    "star_completeness",
)
RISK_STATUSES = {"inferred", "conflicting", "missing", "missing_confirmed", "unsupported"}
RECORD_DIRECTORIES = {
    "project": ("projects", "project_id", "project_name"),
    "experience": ("experiences", "experience_id", "experience_name"),
}


def compact_text(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def compact_generic(value: Any, text_limit: int, list_limit: int = 8) -> Any:
    if isinstance(value, str):
        return compact_text(value, text_limit)
    if isinstance(value, list):
        return [compact_generic(item, text_limit, list_limit) for item in value[:list_limit]]
    if isinstance(value, dict):
        return {
            str(key): compact_generic(item, text_limit, list_limit)
            for key, item in value.items()
            if key != "contact"
        }
    return value


def source_ids(record: dict[str, Any]) -> list[str]:
    values: list[str] = []

    def add_refs(refs: object) -> None:
        if not isinstance(refs, list):
            return
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            source_id = ref.get("source_id")
            if isinstance(source_id, str) and source_id not in values:
                values.append(source_id)

    add_refs(record.get("source_refs"))
    field_evidence = record.get("field_evidence")
    if isinstance(field_evidence, dict):
        for evidence in field_evidence.values():
            if isinstance(evidence, dict):
                add_refs(evidence.get("source_refs"))
    return values


def evidence_summary(record: dict[str, Any], text_limit: int) -> dict[str, Any]:
    field_evidence = record.get("field_evidence")
    counts: Counter[str] = Counter()
    risks: list[dict[str, str]] = []
    if isinstance(field_evidence, dict):
        for field, evidence in field_evidence.items():
            if not isinstance(evidence, dict):
                continue
            status = evidence.get("status")
            if isinstance(status, str):
                counts[status] += 1
                if status in RISK_STATUSES and len(risks) < 12:
                    risk = {"field": str(field), "status": status}
                    notes = evidence.get("notes")
                    if notes:
                        risk["notes"] = compact_text(notes, text_limit)
                    risks.append(risk)
    return {
        "status_counts": dict(sorted(counts.items())),
        "risk_fields": risks,
        "source_ids": source_ids(record),
    }


def compact_metric(metric: object, text_limit: int) -> Any:
    if not isinstance(metric, dict):
        return compact_generic(metric, text_limit)
    keys = (
        "name",
        "value",
        "unit",
        "measurement_type",
        "timeframe",
        "scope",
        "evidence_status",
    )
    return {
        key: compact_generic(metric[key], text_limit)
        for key in keys
        if key in metric and metric[key] not in ("", None, [])
    }


def card_for_record(
    record_type: str,
    record: dict[str, Any],
    text_limit: int,
    max_items: int,
) -> dict[str, Any]:
    _, id_key, name_key = RECORD_DIRECTORIES[record_type]
    card: dict[str, Any] = {
        "record_type": record_type,
        "record_id": record.get(id_key, ""),
        "name": compact_text(record.get(name_key, ""), text_limit),
        "experience_type": record.get("experience_type", ""),
        "organization": compact_text(record.get("organization", ""), text_limit),
        "role": compact_text(record.get("role", ""), text_limit),
        "time_range": compact_text(record.get("time_range", ""), text_limit),
        "record_status": record.get("status", ""),
    }
    for field, field_limit in CARD_FIELDS.items():
        value = record.get(field)
        if not value:
            continue
        if not isinstance(value, list):
            card[field] = compact_generic(value, text_limit)
            continue
        limit = min(field_limit, max_items)
        card[field] = [compact_generic(item, text_limit) for item in value[:limit]]
        if len(value) > limit:
            card[f"{field}_omitted_count"] = len(value) - limit
    metrics = record.get("metrics")
    if isinstance(metrics, list) and metrics:
        metric_limit = min(2, max_items)
        card["metrics"] = [compact_metric(metric, text_limit) for metric in metrics[:metric_limit]]
        if len(metrics) > metric_limit:
            card["metrics_omitted_count"] = len(metrics) - metric_limit
    card["evidence_summary"] = evidence_summary(record, text_limit)
    return card


def detail_for_record(
    record_type: str,
    record: dict[str, Any],
    text_limit: int,
    max_items: int,
    full_details: bool,
) -> dict[str, Any]:
    _, id_key, name_key = RECORD_DIRECTORIES[record_type]
    detail: dict[str, Any] = {
        "record_type": record_type,
        "record_id": record.get(id_key, ""),
        "name": record.get(name_key, ""),
        "experience_type": record.get("experience_type", ""),
        "organization": record.get("organization", ""),
        "role": record.get("role", ""),
        "time_range": record.get("time_range", ""),
        "record_status": record.get("status", ""),
        "detail_mode": "full" if full_details else "delta_from_cards",
    }
    if full_details:
        for field in DETAIL_FIELDS:
            if field in record:
                detail[field] = record[field]
        return detail

    for field, field_limit in CARD_FIELDS.items():
        value = record.get(field)
        if not isinstance(value, list):
            continue
        card_limit = min(field_limit, max_items)
        if len(value) > card_limit:
            detail[f"{field}_continuation"] = value[card_limit:]
    metrics = record.get("metrics")
    if isinstance(metrics, list):
        metric_limit = min(2, max_items)
        if len(metrics) > metric_limit:
            detail["metrics_continuation"] = metrics[metric_limit:]
    for field in ("source_refs", "field_evidence", "star_completeness"):
        if field in record:
            detail[field] = record[field]
    return detail


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def iter_records(root: Path) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    for record_type, (directory_name, _, _) in RECORD_DIRECTORIES.items():
        for path in sorted((root / directory_name).glob("*.json")):
            records.append((record_type, load_json(path)))
    return records


def resolve_requested_records(
    root: Path,
    requested: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    resolved: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for selector in requested:
        if ":" in selector:
            record_type, record_id = selector.split(":", 1)
            if record_type not in RECORD_DIRECTORIES:
                raise ValueError(f"Unknown record type in selector: {selector}")
            candidates = [record_type]
        else:
            record_id = selector
            candidates = list(RECORD_DIRECTORIES)

        matches: list[tuple[str, Path]] = []
        for record_type in candidates:
            directory_name, _, _ = RECORD_DIRECTORIES[record_type]
            path = root / directory_name / f"{record_id}.json"
            if path.is_file():
                matches.append((record_type, path))
        if not matches:
            raise ValueError(f"Record not found: {selector}")
        if len(matches) > 1:
            raise ValueError(f"Ambiguous record selector; include project: or experience:: {selector}")
        record_type, path = matches[0]
        key = (record_type, record_id)
        if key not in seen:
            resolved.append((record_type, load_json(path)))
            seen.add(key)
    return resolved


def compact_profile(root: Path, text_limit: int) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    files = {
        "candidate": root / "profile/candidate-profile.json",
        "education": root / "profile/education.json",
        "skills": root / "profile/skills.json",
        "awards": root / "profile/awards.json",
        "preferences": root / "profile/preferences.json",
    }
    for label, path in files.items():
        if not path.is_file():
            continue
        data = load_json(path)
        if label == "candidate":
            data.pop("contact", None)
            data.pop("field_evidence", None)
            data.pop("source_refs", None)
        profile[label] = compact_generic(data, text_limit)
    return profile


def build_context(
    root: Path,
    requested_records: list[str],
    text_limit: int,
    max_items: int,
    full_details: bool,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    errors, warnings = validate(root)
    if errors:
        concise = "; ".join(errors[:8])
        remainder = len(errors) - min(8, len(errors))
        if remainder:
            concise += f"; … {remainder} more"
        raise ValueError(f"Workspace validation failed: {concise}")

    if requested_records:
        records = resolve_requested_records(root, requested_records)
        mode = "details"
        payload_records = [
            detail_for_record(record_type, record, text_limit, max_items, full_details)
            for record_type, record in records
        ]
    else:
        records = iter_records(root)
        mode = "cards"
        payload_records = [
            card_for_record(record_type, record, text_limit, max_items)
            for record_type, record in records
        ]

    return {
        "schema_version": "match-context-1.0",
        "mode": mode,
        "workspace": str(root),
        "record_count": len(payload_records),
        "warnings": warnings,
        "profile": compact_profile(root, text_limit) if mode == "cards" else {},
        "records": payload_records,
    }


def context_page(payload: dict[str, Any], offset: int, budget: int, pretty: bool) -> str:
    """Page whole records without silently dropping evidence or exceeding budget."""
    records = payload["records"]
    if offset < 0 or (offset >= len(records) and offset != 0):
        raise ValueError("Offset is outside the record list")
    page = dict(payload)
    page["records"] = []
    if offset:
        page["profile"] = {}
    page["total_record_count"] = len(records)
    page["offset"] = offset

    def serialize(end: int) -> str:
        page["record_count"] = len(page["records"])
        page["next_offset"] = end if end < len(records) else None
        page["omitted_record_count"] = len(records) - end
        return json.dumps(page, ensure_ascii=False, indent=2 if pretty else None,
                          separators=None if pretty else (",", ":"))

    output = serialize(offset)
    for index in range(offset, len(records)):
        page["records"].append(records[index])
        candidate = serialize(index + 1)
        if len(candidate) > budget:
            page["records"].pop()
            if not page["records"]:
                raise ValueError(
                    f"Record at offset {offset} with page metadata needs {len(candidate)} "
                    "characters; increase --max-output-chars for this record. "
                    "Evidence was not truncated."
                )
            break
        output = candidate
    if len(output) > budget:
        raise ValueError("Profile/page metadata exceeds budget; increase --max-output-chars")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("workspace"), help="Workspace directory")
    parser.add_argument(
        "--record",
        action="append",
        default=[],
        help="Return detailed evidence for project:<id>, experience:<id>, or an unambiguous id",
    )
    parser.add_argument(
        "--max-items-per-field",
        type=int,
        default=3,
        help="Maximum card items retained per list field",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=280,
        help="Maximum characters retained per text value",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        default=16000,
        help="Character budget per page; oversized single records require explicit expansion",
    )
    parser.add_argument(
        "--full-details",
        action="store_true",
        help="Repeat full selected records instead of returning only data omitted from prior cards",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON for debugging")
    parser.add_argument("--offset", type=int, default=0, help="Resume at next_offset with identical selection and limits")
    args = parser.parse_args()
    if args.max_items_per_field < 1 or args.max_text_chars < 40 or args.max_output_chars < 1000:
        parser.error("Limits must be positive and large enough to preserve usable evidence")

    try:
        payload = build_context(
            args.root,
            args.record,
            args.max_text_chars,
            args.max_items_per_field,
            args.full_details,
        )
        output = context_page(payload, args.offset, args.max_output_chars, args.pretty)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

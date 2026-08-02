from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
ASSETS = SKILL_ROOT / "assets/templates"


def run_script(name: str, *arguments: object, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPTS / name), *(str(value) for value in arguments)]
    return subprocess.run(command, check=check, capture_output=True, text=True)


class MatchWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "workspace"
        run_script("init_workspace.py", "--root", self.root)
        self.write_project()
        result = run_script("validate_workspace.py", "--root", self.root)
        self.assertIn("Validation passed", result.stdout)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_project(self) -> None:
        project = json.loads((ASSETS / "project.json").read_text(encoding="utf-8"))
        project.update(
            {
                "project_id": "sample-project",
                "project_name": "Sample Wearable",
                "experience_type": "research",
                "organization": "Sample Lab",
                "role": "Researcher",
                "time_range": "2025",
                "background": ["A wearable interaction study with a deliberately long description."],
                "actions": [
                    "Interviewed users.",
                    "Defined interaction requirements.",
                    "Tested a prototype.",
                    "Reported findings to the product team.",
                ],
                "deliverables": ["Prototype", "Research report"],
                "results": ["Identified two verified usability issues."],
                "metrics": [
                    {
                        "name": "participants",
                        "value": 8,
                        "unit": "people",
                        "measurement_type": "actual",
                        "timeframe": "2025",
                        "scope": "study",
                        "evidence_status": "verified",
                        "source_refs": [{"source_id": "src-001", "location": "p. 2"}],
                    }
                ],
                "skills": ["user research", "wearables"],
                "tools": ["Python"],
                "source_refs": [{"source_id": "src-001", "location": "p. 2"}],
                "field_evidence": {
                    "actions[0]": {
                        "status": "verified",
                        "source_refs": [{"source_id": "src-001", "location": "p. 2"}],
                        "notes": "",
                    },
                    "results[0]": {
                        "status": "inferred",
                        "source_refs": [{"source_id": "src-001", "location": "p. 2"}],
                        "notes": "Confirm whether the team adopted the finding.",
                    },
                },
                "star_completeness": {
                    "situation": "verified",
                    "task": "verified",
                    "action": "verified",
                    "result": "inferred",
                },
                "status": "usable_with_gaps",
                "updated_at": "2026-07-26T00:00:00Z",
            }
        )
        path = self.root / "projects/sample-project.json"
        path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def start_bundle(self, job_id: str, mode: str = "match") -> Path:
        result = run_script(
            "apply_match_bundle.py",
            "start",
            "--root",
            self.root,
            "--job-id",
            job_id,
            "--mode",
            mode,
            "--task",
            f"Match {job_id}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "started")
        self.assertEqual(payload["mode"], mode)
        return Path(payload["bundle_dir"])

    def write_bundle(self, bundle_dir: Path, job_id: str, evidence_status: str = "verified") -> None:
        manifest = {
            "schema_version": "match-bundle-1.0",
            "job_id": job_id,
            "mode": "match",
            "source_catalog_upserts": [
                {
                    "source_id": "src-001",
                    "source_type": "job_description",
                    "file_name": "job.txt",
                    "path": "workspace/inbox/job.txt",
                    "parse_status": "complete",
                    "related_projects": ["sample-project"],
                    "version_of": None,
                    "notes": "",
                }
            ],
            "run_manifest_patch": {
                "available_inputs": [{"path": "workspace/inbox/job.txt", "type": "job_description"}],
                "missing_inputs": [],
                "planned_stages": ["analyze-job", "match"],
                "completed_stages": ["analyze-job", "match"],
                "status": "complete",
                "limitations": [],
                "updated_at": "2026-07-26T00:00:00Z",
            },
            "change_log_entries": [
                {
                    "timestamp": "2026-07-26T00:00:00Z",
                    "operation": "analyze-job-and-match",
                    "job_id": job_id,
                }
            ],
        }
        metadata = {
            "job_id": job_id,
            "company": "Sample",
            "role": "Product Manager",
            "location": "Remote",
            "source_url": "",
            "user_version": True,
            "web_verified": False,
            "accessed_at": "2026-07-26",
            "target_language": "en",
            "page_limit": 1,
        }
        analysis = {
            "job_id": job_id,
            "role_objective": ["Build wearable software products."],
            "responsibilities": ["Define requirements."],
            "must_have": ["User research"],
            "nice_to_have": ["Wearables"],
            "competencies": ["Product judgment"],
            "keywords": ["wearable"],
            "hard_constraints": [],
            "inferred_requirements": [],
            "priority_weights": [],
        }
        matrix = {
            "job_id": job_id,
            "requirements": [
                {
                    "requirement": "Define wearable product requirements",
                    "priority": 5,
                    "matched_records": [
                        {"record_type": "project", "record_id": "sample-project"}
                    ],
                    "evidence": ["Defined interaction requirements from user research."],
                    "source_refs": [{"source_id": "src-001", "location": "p. 2"}],
                    "evidence_status": evidence_status,
                    "score_breakdown": {
                        "jd_relevance": 90,
                        "evidence_strength": 80,
                        "candidate_ownership": 70,
                        "result_impact": 60,
                        "differentiation": 50,
                        "keyword_coverage": 40,
                    },
                    "match_score": 0,
                    "resume_recommendation": "include",
                    "risk": "Adoption is not confirmed.",
                    "interview_follow_up": ["How did the requirements change?"],
                }
            ],
            "record_ranking": [],
            "uncovered_requirements": [],
            "weak_evidence": [],
        }
        files: dict[str, object] = {
            "manifest.json": manifest,
            "job-metadata.json": metadata,
            "jd-analysis.json": analysis,
            "evidence-matrix.json": matrix,
        }
        for name, value in files.items():
            (bundle_dir / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        (bundle_dir / "jd-original.md").write_text("# Sample JD\n", encoding="utf-8")
        (bundle_dir / "jd-analysis-summary.md").write_text(
            "# Match summary\n\nSample project is relevant.\n",
            encoding="utf-8",
        )

    def test_prepare_context_compacts_cards_and_expands_selected_record(self) -> None:
        cards_result = run_script("prepare_match_context.py", "--root", self.root)
        cards = json.loads(cards_result.stdout)
        self.assertEqual(cards["mode"], "cards")
        self.assertEqual(cards["record_count"], 1)
        self.assertNotIn("contact", cards["profile"]["candidate"])
        card = cards["records"][0]
        self.assertNotIn("field_evidence", card)
        self.assertEqual(card["actions_omitted_count"], 1)
        self.assertEqual(card["evidence_summary"]["status_counts"]["inferred"], 1)

        detail_result = run_script(
            "prepare_match_context.py",
            "--root",
            self.root,
            "--record",
            "project:sample-project",
        )
        details = json.loads(detail_result.stdout)
        self.assertEqual(details["mode"], "details")
        self.assertIn("field_evidence", details["records"][0])
        self.assertEqual(details["records"][0]["detail_mode"], "delta_from_cards")
        self.assertEqual(len(details["records"][0]["actions_continuation"]), 1)
        self.assertNotIn("actions", details["records"][0])

        full_detail_result = run_script(
            "prepare_match_context.py",
            "--root",
            self.root,
            "--record",
            "project:sample-project",
            "--full-details",
        )
        full_details = json.loads(full_detail_result.stdout)
        self.assertEqual(full_details["records"][0]["detail_mode"], "full")
        self.assertEqual(len(full_details["records"][0]["actions"]), 4)

    def test_bundle_apply_is_validated_scored_and_idempotent(self) -> None:
        job_id = "sample-product-manager"
        bundle_dir = self.start_bundle(job_id)
        self.write_bundle(bundle_dir, job_id)

        dry_run = run_script(
            "apply_match_bundle.py",
            "apply",
            "--root",
            self.root,
            "--bundle-dir",
            bundle_dir,
            "--dry-run",
        )
        dry_payload = json.loads(dry_run.stdout)
        self.assertEqual(dry_payload["status"], "valid")
        self.assertEqual(dry_payload["normalized_scores"], 1)
        self.assertFalse((self.root / f"jobs/{job_id}/evidence-matrix.json").exists())

        first_apply = run_script(
            "apply_match_bundle.py",
            "apply",
            "--root",
            self.root,
            "--bundle-dir",
            bundle_dir,
        )
        first_payload = json.loads(first_apply.stdout)
        self.assertEqual(first_payload["status"], "applied")
        matrix = json.loads(
            (self.root / f"jobs/{job_id}/evidence-matrix.json").read_text(encoding="utf-8")
        )
        self.assertEqual(matrix["requirements"][0]["match_score"], 75)

        second_apply = run_script(
            "apply_match_bundle.py",
            "apply",
            "--root",
            self.root,
            "--bundle-dir",
            bundle_dir,
            "--consume",
        )
        second_payload = json.loads(second_apply.stdout)
        self.assertEqual(second_payload["changed"], [])
        self.assertTrue(second_payload["bundle_consumed"])
        self.assertFalse(bundle_dir.exists())

        change_lines = [
            line
            for line in (self.root / "state/change-log.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        self.assertEqual(len(change_lines), 1)
        result = run_script("validate_workspace.py", "--root", self.root)
        self.assertIn("Validation passed", result.stdout)

    def test_invalid_evidence_status_is_rejected_before_writes(self) -> None:
        job_id = "invalid-status-role"
        bundle_dir = self.start_bundle(job_id)
        self.write_bundle(bundle_dir, job_id, evidence_status="partial")
        result = run_script(
            "apply_match_bundle.py",
            "apply",
            "--root",
            self.root,
            "--bundle-dir",
            bundle_dir,
            "--dry-run",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        error = json.loads(result.stdout)
        self.assertEqual(error["status"], "error")
        self.assertIn("evidence_status", error["error"])
        self.assertFalse((self.root / f"jobs/{job_id}").exists())

    def test_analyze_job_mode_does_not_require_evidence_matrix(self) -> None:
        job_id = "analysis-only-role"
        bundle_dir = self.start_bundle(job_id, mode="analyze-job")
        self.write_bundle(bundle_dir, job_id)
        manifest_path = bundle_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["mode"] = "analyze-job"
        manifest["run_manifest_patch"]["planned_stages"] = ["analyze-job"]
        manifest["run_manifest_patch"]["completed_stages"] = ["analyze-job"]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (bundle_dir / "evidence-matrix.json").unlink()

        result = run_script(
            "apply_match_bundle.py",
            "apply",
            "--root",
            self.root,
            "--bundle-dir",
            bundle_dir,
            "--consume",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "applied")
        self.assertTrue((self.root / f"jobs/{job_id}/jd-analysis.json").is_file())
        self.assertFalse((self.root / f"jobs/{job_id}/evidence-matrix.json").exists())


if __name__ == "__main__":
    unittest.main()

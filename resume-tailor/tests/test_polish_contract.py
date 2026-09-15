from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


class PolishContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "workspace"
        subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts/init_workspace.py"), "--root", str(self.root)],
            check=True,
            capture_output=True,
            text=True,
        )
        project = json.loads((SKILL_DIR / "assets/templates/project.json").read_text(encoding="utf-8"))
        project.update(
            {
                "project_id": "sample-project",
                "project_name": "Sample Project",
                "experience_type": "personal",
                "actions": ["Built a prototype"],
                "deliverables": ["Prototype"],
                "field_evidence": {
                    "actions[0]": {"status": "verified", "source_refs": [], "notes": ""}
                },
            }
        )
        (self.root / "projects/sample-project.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.job_dir = self.root / "jobs/sample-role"
        self.job_dir.mkdir()
        matrix = json.loads(
            (SKILL_DIR / "assets/templates/evidence-matrix.json").read_text(encoding="utf-8")
        )
        matrix["job_id"] = "sample-role"
        self.matrix_path = self.job_dir / "evidence-matrix.json"
        self.matrix_path.write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def tailoring_payload(self, evidence_status: str = "verified") -> dict:
        return {
            "job_id": "sample-role",
            "source_evidence_matrix_sha256": hashlib.sha256(self.matrix_path.read_bytes()).hexdigest(),
            "role_narrative": {
                "core_problem": "Build reliable products",
                "priority_signals": ["delivery"],
                "expected_outputs": ["prototype"],
                "supported_keywords": ["prototype"],
                "unsafe_terms": [],
            },
            "records": [
                {
                    "record_type": "project",
                    "record_id": "sample-project",
                    "positioning": "Shows product delivery",
                    "requirement_refs": ["prototype delivery"],
                    "primary_signals": ["delivery"],
                    "supporting_signals": [],
                    "evidence_selection": [
                        {
                            "field_paths": ["actions[0]"],
                            "source_refs": [{"source_id": "src-001", "location": "test"}],
                            "evidence_status": evidence_status,
                            "intended_signal": "delivery",
                            "ownership": "individual",
                            "measurement_type": None,
                        }
                    ],
                    "bullet_candidates": [
                        {
                            "bullet_id": "sample-project-bullet-1",
                            "draft": "Built a prototype",
                            "primary_signal": "delivery",
                            "requirement_refs": ["prototype delivery"],
                            "field_paths": ["actions[0]"],
                            "source_refs": [{"source_id": "src-001", "location": "test"}],
                            "evidence_status": evidence_status,
                            "keyword_alignment": ["prototype"],
                            "ownership": "individual",
                            "risk_notes": [],
                            "selection_status": "selected",
                        }
                    ],
                    "excluded_evidence": [],
                }
            ],
            "cross_record_strategy": {
                "primary_narrative": "Product delivery",
                "coverage_allocation": [],
                "deduplication_decisions": [],
            },
            "unresolved_questions": [],
            "updated_at": "2026-09-15T00:00:00Z",
        }

    def validate(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts/validate_workspace.py"), "--root", str(self.root)],
            capture_output=True,
            text=True,
        )

    def test_valid_tailoring_contract(self) -> None:
        (self.job_dir / "experience-tailoring.json").write_text(
            json.dumps(self.tailoring_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_selected_bullet_rejects_unconfirmed_evidence(self) -> None:
        (self.job_dir / "experience-tailoring.json").write_text(
            json.dumps(self.tailoring_payload("inferred"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Selected bullet has unusable evidence_status", result.stdout)

    def test_tailoring_rejects_stale_evidence_matrix(self) -> None:
        payload = self.tailoring_payload()
        (self.job_dir / "experience-tailoring.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.matrix_path.write_text(self.matrix_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("experience-tailoring.json is stale", result.stdout)


if __name__ == "__main__":
    unittest.main()

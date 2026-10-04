"""
KisanOS — Crop Agent Comprehensive Test Suite
Module: agents/crop/test_agent.py

Validates 100% compliance with KisanOS Multi-Agent Contract v2.0:
- Mandatory fields
- RFC-4122 UUID validation
- Enum constraints (status, evidence_band, source_status)
- ISO-8601 timestamps
- Zero chemical / dosage safety policy
- Zero automatic irrigation commands
- Multi-stage wheat scenario testing
- Unsupported crop handling
- AI enhancement block structure

Run via: python test_agent.py OR pytest test_agent.py -v
"""

import sys
import os
import unittest
import uuid
import re
from datetime import datetime

# Ensure local imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from schema import (
        CropAgentResponse, SourceRecord,
        PROHIBITED_CHEMICAL_KEYWORDS,
        validate_crop_payload, _validate_uuid,
    )
    from agent import CropAgent, WHEAT_GROWTH_STAGES, WHEAT_STRESS_KNOWLEDGE_BASE, normalize_symptoms
    from ai_enhance import get_deterministic_urdu_enhancement
except ImportError:
    from .schema import (
        CropAgentResponse, SourceRecord,
        PROHIBITED_CHEMICAL_KEYWORDS,
        validate_crop_payload, _validate_uuid,
    )
    from .agent import CropAgent, WHEAT_GROWTH_STAGES, WHEAT_STRESS_KNOWLEDGE_BASE, normalize_symptoms
    from .ai_enhance import get_deterministic_urdu_enhancement


class TestCropAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.agent = CropAgent(crop_type="wheat")
        # Standard wheat tillering scenario
        cls.response = cls.agent.analyze(
            crop="wheat",
            growth_stage="tillering",
            days_since_irrigation=5,
            symptoms=["yellowing leaves", "stunted growth"],
            tehsil_or_coords="bahawalpur_sadar",
            enable_ai=False,
        )
        cls.response_dict = cls.response.model_dump()

    # ─── CONTRACT COMPLIANCE TESTS ───
    def test_01_mandatory_fields_present(self):
        """Rule 1: All canonical contract fields must exist."""
        required = [
            "agent_id", "assessment_id", "status", "summary", "observations",
            "possible_causes", "checks", "evidence_band", "evidence_reason",
            "sources", "provider_or_model", "version", "created_at", "safety_flags",
        ]
        for field in required:
            self.assertIn(field, self.response_dict, f"Missing required field: {field}")
        self.assertEqual(self.response.agent_id, "crop")

    def test_02_valid_uuid_generated(self):
        """Rule: assessment_id must be a valid RFC-4122 UUID."""
        clean_uuid = self.response.assessment_id
        parsed = uuid.UUID(clean_uuid)
        self.assertEqual(str(parsed), clean_uuid.lower())

    def test_03_explicit_valid_uuid_accepted(self):
        """Test that an explicit valid UUID is accepted."""
        test_uuid = "a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d"
        res = self.agent.analyze(assessment_id=test_uuid, enable_ai=False)
        self.assertEqual(res.assessment_id, test_uuid)

    def test_04_invalid_uuid_rejected(self):
        """Contract: Invalid UUID strings must be strictly rejected."""
        invalid_uuids = [
            "not-a-uuid", "12345", "invalid-uuid-with-wrong-length", "", None
        ]
        for bad in invalid_uuids:
            with self.assertRaises(ValueError, msg=f"Should reject: {bad!r}"):
                if bad is None:
                    _validate_uuid(bad)
                else:
                    self.agent.analyze(assessment_id=bad, enable_ai=False)

    def test_05_missing_mandatory_fields_rejected(self):
        """Contract: Missing any mandatory field must fail schema validation."""
        valid_sample = dict(self.response_dict)
        for key in ["assessment_id", "status", "summary", "sources", "created_at", "evidence_band"]:
            corrupted = dict(valid_sample)
            del corrupted[key]
            with self.assertRaises(Exception, msg=f"Should reject payload missing: {key}"):
                validate_crop_payload(corrupted)

    def test_06_status_enum_validity(self):
        """Rule 2: Status must be complete/partial/unavailable/error."""
        valid = {"complete", "partial", "unavailable", "error"}
        self.assertIn(self.response.status, valid)

        for bad in ["success", "failed", "pending", "in_progress"]:
            corrupted = dict(self.response_dict)
            corrupted["status"] = bad
            with self.assertRaises(ValueError, msg=f"Should reject status: {bad}"):
                validate_crop_payload(corrupted)

    def test_07_evidence_band_enum_validity(self):
        """Rule 3: Evidence band must be low/medium/high/not_calibrated."""
        valid = {"low", "medium", "high", "not_calibrated"}
        self.assertIn(self.response.evidence_band, valid)

        for bad in ["extreme", "very_high", "confident"]:
            corrupted = dict(self.response_dict)
            corrupted["evidence_band"] = bad
            with self.assertRaises(ValueError, msg=f"Should reject evidence_band: {bad}"):
                validate_crop_payload(corrupted)

    def test_08_source_status_enum_validity(self):
        """Contract: Source status must be official/supporting/secondary/unverified."""
        valid = {"official", "supporting", "secondary", "unverified"}
        for src in self.response.sources:
            status_val = src["source_status"] if isinstance(src, dict) else src.source_status
            self.assertIn(status_val, valid)

        with self.assertRaises(ValueError):
            SourceRecord(
                title="Test", url="https://example.com", publisher="Test",
                retrieved_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                source_status="unrated",
            )

    def test_09_iso8601_timestamps(self):
        """Rule 6: All timestamps must be ISO-8601 compliant."""
        clean = self.response.created_at.replace("Z", "+00:00")
        self.assertIsNotNone(datetime.fromisoformat(clean))

        for src in self.response.sources:
            retrieved = src["retrieved_at"] if isinstance(src, dict) else src.retrieved_at
            clean_retrieved = retrieved.replace("Z", "+00:00")
            self.assertIsNotNone(datetime.fromisoformat(clean_retrieved))

    # ─── SAFETY POLICY TESTS ───
    def test_10_zero_chemical_and_dosage_safety(self):
        """Rule 4: Zero chemical, pesticide, fertilizer or dose mentions."""
        corpus = (
            self.response.summary + " " +
            " ".join(self.response.observations) + " " +
            " ".join(self.response.possible_causes) + " " +
            " ".join(self.response.checks)
        ).lower()

        for prohibited in PROHIBITED_CHEMICAL_KEYWORDS:
            pattern = r'\b' + re.escape(prohibited) + r'\b'
            matches = re.findall(pattern, corpus)
            self.assertEqual(
                len(matches), 0,
                f"SAFETY VIOLATION: Prohibited term '{prohibited}' found in output!"
            )

    def test_11_zero_automatic_irrigation_command(self):
        """PRD: Never output exact irrigation command like 'irrigate now'."""
        corpus = (self.response.summary + " " + " ".join(self.response.checks)).lower()
        self.assertNotIn("irrigate now", corpus)
        self.assertNotIn("turn on pump", corpus)

    def test_12_sources_properly_formatted(self):
        """Sources must have valid URLs and official/supporting status."""
        self.assertGreater(len(self.response.sources), 0)
        for src in self.response.sources:
            title = src["title"] if isinstance(src, dict) else src.title
            url = src["url"] if isinstance(src, dict) else src.url
            status = src["source_status"] if isinstance(src, dict) else src.source_status
            retrieved = src["retrieved_at"] if isinstance(src, dict) else src.retrieved_at

            self.assertTrue(title)
            self.assertTrue(url.startswith("http"))
            self.assertIn(status, {"official", "supporting", "secondary", "unverified"})
            clean_ts = retrieved.replace("Z", "+00:00")
            self.assertIsNotNone(datetime.fromisoformat(clean_ts))

    # ─── CROP-SPECIFIC TESTS ───
    def test_13_growth_stage_auto_detection(self):
        """Test growth stage auto-detection from sowing date."""
        # Sowing date ~90 days ago → should be in heading/flowering range
        res = self.agent.analyze(
            crop="wheat",
            sowing_date="2026-07-05",  # ~90 days ago from 2026-10-03
            enable_ai=False,
        )
        self.assertIn(
            res.crop_details.growth_stage,
            {"heading", "flowering", "booting", "grain_fill"},
        )
        self.assertIsNotNone(res.crop_details.days_since_sowing)

    def test_14_symptom_normalization(self):
        """Test that farmer free-text symptoms map to KB keys."""
        matched = normalize_symptoms(["yellowing leaves", "wilting", "random text"])
        self.assertIn("yellowing_lower_leaves", matched)
        self.assertIn("wilting", matched)

    def test_15_multiple_stages_covered(self):
        """Test analysis works across all wheat growth stages."""
        stages = ["germination", "tillering", "booting", "heading", "flowering", "grain_fill", "maturity"]
        for stage in stages:
            res = self.agent.analyze(
                crop="wheat",
                growth_stage=stage,
                symptoms=["wilting"],
                enable_ai=False,
            )
            self.assertEqual(res.crop_details.growth_stage, stage)
            self.assertEqual(res.status, "complete")

    def test_16_unsupported_crop_handling(self):
        """Unsupported crops must return partial status with safety flag."""
        res = self.agent.analyze(
            crop="rice",  # not supported in MVP
            growth_stage="tillering",
            symptoms=["yellowing leaves"],
            enable_ai=False,
        )
        self.assertEqual(res.status, "partial")
        self.assertTrue(any("UNSUPPORTED_CROP" in f for f in res.safety_flags))

    def test_17_days_since_irrigation_high_gap(self):
        """Test guidance for high irrigation gap."""
        res = self.agent.analyze(
            crop="wheat",
            growth_stage="tillering",
            days_since_irrigation=15,  # high gap
            symptoms=["wilting"],
            enable_ai=False,
        )
        # Should mention irrigation gap in causes or checks
        full_text = " ".join(res.possible_causes) + " ".join(res.checks)
        self.assertIn("15", full_text)

    def test_18_ai_enhanced_structure(self):
        """Verify AI enhancement block structure."""
        sample = {
            "crop": "wheat",
            "growth_stage": "tillering",
            "days_since_irrigation": 5,
            "symptoms": ["yellowing leaves"],
            "severity": "moderate",
            "tehsil": "Bahawalpur",
        }
        ai_data = get_deterministic_urdu_enhancement(sample)
        self.assertIn("urdu_summary", ai_data)
        self.assertIn("roman_urdu", ai_data)
        self.assertIn("audio_script_urdu", ai_data)
        self.assertIn("emoji_visual", ai_data)
        self.assertIn("farmer_explanation", ai_data)
        self.assertIn(ai_data["priority_level"], {"high", "medium", "low"})

    def test_19_knowledge_base_integrity(self):
        """Each KB entry must have required fields."""
        for key, entry in WHEAT_STRESS_KNOWLEDGE_BASE.items():
            self.assertIn("aliases", entry, f"KB '{key}' missing aliases")
            self.assertIn("possible_causes", entry, f"KB '{key}' missing causes")
            self.assertIn("checks", entry, f"KB '{key}' missing checks")
            self.assertIn("severity_hint", entry, f"KB '{key}' missing severity_hint")
            self.assertGreater(len(entry["checks"]), 0)
            self.assertGreater(len(entry["possible_causes"]), 0)

    def test_20_growth_stages_complete(self):
        """All required wheat growth stages present in order."""
        stages = [s["stage"] for s in WHEAT_GROWTH_STAGES]
        expected = ["germination", "tillering", "booting", "heading", "flowering", "grain_fill", "maturity"]
        self.assertEqual(stages, expected)


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCropAgent)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print(f"\n✅ ALL {result.testsRun} KISANOS CROP AGENT TESTS PASSED SUCCESSFULLY!")
        return 0
    else:
        print(f"\n❌ SOME TESTS FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
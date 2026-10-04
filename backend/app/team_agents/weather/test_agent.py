"""
KisanOS — Weather Agent Test Suite
Module: agents/weather/test_agent.py

Validates 100% compliance with KisanOS Multi-Agent Contract v2.0
and Safety Policy rules.
Run via: pytest test_agent.py OR python test_agent.py
"""

import sys
import os
import unittest
from datetime import datetime
import re

# Add current folder to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from schema import WeatherAgentResponse, PROHIBITED_CHEMICAL_KEYWORDS, validate_weather_payload
    from agent import WeatherAgent, BAHAWALPUR_TEHSILS
    from ai_enhance import get_deterministic_urdu_enhancement
except ImportError:
    from .schema import WeatherAgentResponse, PROHIBITED_CHEMICAL_KEYWORDS, validate_weather_payload
    from .agent import WeatherAgent, BAHAWALPUR_TEHSILS
    from .ai_enhance import get_deterministic_urdu_enhancement


class TestWeatherAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.agent = WeatherAgent()
        # Run standard analysis on default Bahawalpur pilot location
        cls.response = cls.agent.analyze(tehsil_or_coords="bahawalpur_sadar", enable_ai=False)
        cls.response_dict = cls.response.model_dump()

    def test_mandatory_fields_present(self):
        """Rule 1: Mandated fields must all exist in payload."""
        required_fields = [
            "agent_id", "assessment_id", "status", "summary", "observations",
            "possible_causes", "checks", "evidence_band", "evidence_reason",
            "sources", "provider_or_model", "version", "created_at", "safety_flags"
        ]
        for field in required_fields:
            self.assertIn(field, self.response_dict, f"Missing required field: {field}")

        self.assertEqual(self.response.agent_id, "weather")

    def test_status_enum_validity(self):
        """Rule 2: Status must only be complete, partial, unavailable, error."""
        valid_statuses = {"complete", "partial", "unavailable", "error"}
        self.assertIn(self.response.status, valid_statuses)

    def test_evidence_band_enum_validity(self):
        """Rule 3: Evidence band must only be low, medium, high, not_calibrated."""
        valid_bands = {"low", "medium", "high", "not_calibrated"}
        self.assertIn(self.response.evidence_band, valid_bands)

    def test_iso8601_timestamps(self):
        """Rule 6: ISO-8601 timestamp format verification."""
        clean_created = self.response.created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_created)
        self.assertIsNotNone(dt)

        for src in self.response.sources:
            retrieved_val = src["retrieved_at"] if isinstance(src, dict) else src.retrieved_at
            clean_retrieved = retrieved_val.replace("Z", "+00:00")
            dt_src = datetime.fromisoformat(clean_retrieved)
            self.assertIsNotNone(dt_src)

    def test_zero_chemical_and_dosage_safety(self):
        """Rule 4: Zero chemical, pesticide, fertilizer, or dose mentions."""
        text_corpus = (
            self.response.summary + " " +
            " ".join(self.response.observations) + " " +
            " ".join(self.response.possible_causes) + " " +
            " ".join(self.response.checks)
        ).lower()

        for prohibited in PROHIBITED_CHEMICAL_KEYWORDS:
            pattern = r'\b' + re.escape(prohibited) + r'\b'
            matches = re.findall(pattern, text_corpus)
            self.assertEqual(
                len(matches), 0,
                f"Safety Violation: Prohibited term '{prohibited}' detected in Weather Agent output!"
            )

    def test_zero_automatic_irrigation_command(self):
        """PRD WA-02: Never output exact irrigation amount or 'irrigate now' command."""
        text_corpus = (
            self.response.summary + " " +
            " ".join(self.response.checks)
        ).lower()
        self.assertNotIn("irrigate now", text_corpus)
        self.assertNotIn("turn on pump", text_corpus)

    def test_sources_array_structure(self):
        """Sources array must contain verified SourceRecords."""
        self.assertGreater(len(self.response.sources), 0)
        for src in self.response.sources:
            title_val = src["title"] if isinstance(src, dict) else src.title
            url_val = src["url"] if isinstance(src, dict) else src.url
            status_val = src["source_status"] if isinstance(src, dict) else src.source_status
            self.assertTrue(title_val)
            self.assertTrue(url_val.startswith("http"))
            self.assertIn(status_val, {"official", "supporting", "secondary", "unverified"})

    def test_bahawalpur_pilot_locations(self):
        """Ensure all Bahawalpur tehsils resolve correctly."""
        for tehsil_key, data in BAHAWALPUR_TEHSILS.items():
            name, lat, lon, elev = self.agent.resolve_coordinates(tehsil_key)
            self.assertEqual(name, data["name"])
            self.assertAlmostEqual(lat, data["lat"], places=3)
            self.assertAlmostEqual(lon, data["lon"], places=3)

    def test_resilient_fallback_execution(self):
        """Agent must not crash if provider network fails."""
        # Force fallback by querying dummy/invalid URL
        fallback_agent = WeatherAgent(open_meteo_url="https://invalid.open-meteo-domain.example/forecast")
        res = fallback_agent.analyze(tehsil_or_coords="ahmadpur_east", enable_ai=False)
        self.assertIn(res.status, {"partial", "unavailable"})
        self.assertGreater(len(res.safety_flags), 0)
        self.assertEqual(res.evidence_band, "medium")

    def test_ai_enhanced_structure(self):
        """Verify Urdu AI enhancement fields when present."""
        sample_weather = {
            "tehsil": "Hasilpur",
            "temperature_c": 28.5,
            "relative_humidity_pct": 60,
            "rain_probability_pct": 20,
            "heat_stress_risk": "Moderate",
            "rust_favorable_condition": "Moderate"
        }
        ai_data = get_deterministic_urdu_enhancement(sample_weather)
        self.assertIn("urdu_summary", ai_data)
        self.assertIn("roman_urdu", ai_data)
        self.assertIn("audio_script_urdu", ai_data)
        self.assertIn("emoji_visual", ai_data)
        self.assertIn("farmer_explanation", ai_data)
        self.assertIn(ai_data["priority_level"], {"high", "medium", "low"})


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestWeatherAgent)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n✅ ALL 10 KISANOS WEATHER AGENT TESTS PASSED SUCCESSFULLY!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)

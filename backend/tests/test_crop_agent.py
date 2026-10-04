"""Tests for the deterministic Crop Agent (backend/app/agents/crop.py).

Covers: wheat-only scope, safe hypothesis language, farmer-answerable
non-chemical checks, expert-review referral triggers, Vision gating and
evidence separation, conservative defaults, AgentResult validity and check
limits, and source honesty (no fabricated URLs/sources).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest

from app.agents.crop import VERSION, assess_crop
from app.core.sources import source_registry
from app.schemas import AgentResult

AID = "11111111-1111-4111-8111-111111111111"

# Any of these appearing in Crop output would violate the PRD safety contract:
# products, doses, spray schedules, chemical instructions, irrigation commands,
# guaranteed outcomes, confirmed diagnoses, or named disease/deficiency claims.
FORBIDDEN = re.compile(
    r"\b(pesticides?|fungicides?|insecticides?|herbicides?|spray(?:s|ed|ing)?|doses?|dosage|"
    r"fertili[sz]ers?|urea|dap|npk|potash|nitrogen|phosphorus|potassium|sulphur|sulfur|zinc|"
    r"irrigate\s+now|irrigation\s+command|guaranteed|yield\s+loss|confirmed|deficiency|"
    r"puccinia|blumeria|stripe\s+rust|leaf\s+rust|powdery\s+mildew)\b"
    r"|کیڑے\s?مار|سپرے|کھاد|زرعی\s?دوا|دوائی|ڈوز",
    re.IGNORECASE,
)

# Numeric quantity + unit patterns (doses, rates, irrigation amounts).
QUANTITY = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:kg|ml|litres?|liters?|gallons?|mm|cm|acre|hours?|hrs?|days?)\b",
    re.IGNORECASE,
)

TEXT_KEYS = (
    "summary",
    "observations",
    "possible_causes",
    "checks",
    "evidence_band",
    "evidence_reason",
    "safety_flags",
    "input_evidence",
    "data",
)


def _intake(**overrides: object) -> dict:
    base: dict = {
        "area_code": "bahawalpur_sadar",
        "crop": "wheat",
        "growth_stage": "tillering",
        "sowing_date": None,
        "soil_moisture": "not_sure",
        "symptoms": ["yellowing"],
        "symptoms_spreading": "not_sure",
        "drainage": "not_sure",
        "notes": "",
    }
    base.update(overrides)
    return base


def _vision(status: str = "complete", observations: list | None = None) -> AgentResult:
    return AgentResult(
        assessment_id=AID,
        agent_id="vision",
        status=status,
        summary="vision fixture",
        observations=observations if observations is not None else ["Pale streaks along the leaf blade"],
        possible_causes=[],
        checks=[],
        evidence_band="low",
        evidence_reason="fixture only",
        sources=[],
        provider_or_model="vision-fixture",
        version="vision-fixture-1.0.0",
        created_at=datetime.now(UTC),
    )


def _dump_text(result: AgentResult) -> str:
    dump = result.model_dump(mode="json")
    return json.dumps({k: dump[k] for k in TEXT_KEYS}, ensure_ascii=False)


def _sid(overrides: dict) -> str:
    """Sanitized, unique pytest id for an intake override dict."""
    raw = "_".join(f"{k}_{overrides[k]}" for k in sorted(overrides))
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_") or "empty"


# Input batteries reused by several tests.
SCENARIOS: list[dict] = [
    {"symptoms": ["yellowing"]},
    {"symptoms": ["spots"]},
    {"symptoms": ["rust_like"], "symptoms_spreading": "yes"},
    {"symptoms": ["drying", "insects"]},
    {"symptoms": ["unknown"]},
    {"symptoms": ["lodging"]},
    {"symptoms": []},
    {"symptoms": ["yellowing"], "notes": "Should I spray something? What dose?"},
    {"symptoms": ["spray karun kya?"], "notes": ""},
    {"symptoms": ["wilting"], "growth_stage": "heading", "soil_moisture": "wet"},
    {"symptoms": ["yellowing"], "symptoms_spreading": "yes", "drainage": "poor"},
    {"symptoms": ["mildew_like", "spots"], "growth_stage": "dough"},
]


# ---------------------------------------------------------------------------
# 1. Wheat-only scope enforcement
# ---------------------------------------------------------------------------
def test_crop_enforces_wheat_only_scope():
    result = assess_crop(AID, _intake(crop="rice"), None)
    assert result.status == "unsupported"
    assert result.possible_causes == []
    assert result.data["referral_recommended"] is True
    assert result.data["referral_reasons"] == ["unsupported_crop_scope"]
    assert not FORBIDDEN.search(_dump_text(result))

    # A missing crop must abstain too, not silently fall back to wheat.
    no_crop = assess_crop(AID, _intake(crop=""), None)
    assert no_crop.status == "unsupported"
    assert no_crop.evidence_band == "not_calibrated"


# ---------------------------------------------------------------------------
# 2. Farmer-reported yellowing -> safe hypothesis, not diagnosis
# ---------------------------------------------------------------------------
def test_farmer_yellowing_yields_safe_hypothesis_not_diagnosis():
    result = assess_crop(AID, _intake(symptoms=["yellowing"]), None)
    assert result.status == "complete"
    assert result.evidence_band == "low"
    assert "Possible water stress" in result.possible_causes
    assert "Possible nutrient stress" in result.possible_causes
    text = _dump_text(result)
    assert not FORBIDDEN.search(text)
    assert "confirmed" not in text.lower()
    assert "not a probability or diagnosis" in result.evidence_reason


# ---------------------------------------------------------------------------
# 3. Farmer-reported spots -> non-chemical checks, referral note last
# ---------------------------------------------------------------------------
def test_farmer_spots_produce_non_chemical_checks():
    result = assess_crop(AID, _intake(symptoms=["spots"]), None)
    assert any("Inspect both sides" in c for c in result.checks)
    assert not FORBIDDEN.search(_dump_text(result))
    # Non-chemical field checks always come before the safety/referral note.
    note_positions = [i for i, c in enumerate(result.checks) if "agriculture officer" in c]
    assert note_positions, "single-source (low) evidence must carry an expert-review note"
    assert note_positions[0] == len(result.checks) - 1
    for check in result.checks[:-1]:
        assert "agriculture officer" not in check


# ---------------------------------------------------------------------------
# 4. Rust-like symptom -> expert review referral
# ---------------------------------------------------------------------------
def test_rust_like_symptom_triggers_expert_review():
    result = assess_crop(AID, _intake(symptoms=["rust_like"]), None)
    assert result.data["referral_recommended"] is True
    assert "rust_like_pustules_reported_or_observed" in result.data["referral_reasons"]
    assert any("agriculture officer" in c for c in result.checks)


# ---------------------------------------------------------------------------
# 5. Rapidly spreading symptoms -> expert review referral
# ---------------------------------------------------------------------------
def test_rapid_spreading_triggers_expert_review():
    result = assess_crop(AID, _intake(symptoms=["yellowing"], symptoms_spreading="yes"), None)
    assert result.data["referral_recommended"] is True
    assert "symptoms_rapidly_spreading" in result.data["referral_reasons"]
    assert any("spreading from the edge" in c for c in result.checks)


# ---------------------------------------------------------------------------
# 6. Vision complete -> consumed safely (and referral is not blanket-on)
# ---------------------------------------------------------------------------
def test_vision_complete_is_consumed_safely():
    vision = _vision("complete", ["Pale streaks along the leaf blade"])
    result = assess_crop(AID, _intake(symptoms=["yellowing"]), vision)
    assert result.status == "complete"
    assert result.data["vision_used"] is True
    assert result.data["vision_status"] == "complete"
    assert result.evidence_band == "medium"
    assert any(o.startswith("Photo visible:") for o in result.observations)
    # Medium evidence with no trigger conditions -> no blanket referral.
    assert result.data["referral_recommended"] is False
    assert result.data["referral_reasons"] == []
    assert not FORBIDDEN.search(_dump_text(result))


# ---------------------------------------------------------------------------
# 7. Vision not_assessed -> Crop continues on farmer symptoms only
# ---------------------------------------------------------------------------
def test_vision_not_assessed_does_not_break_crop():
    vision = _vision("not_assessed", ["would-be observation"])
    result = assess_crop(AID, _intake(symptoms=["yellowing"]), vision)
    assert result.status == "complete"
    assert result.data["vision_used"] is False
    assert result.data["vision_status"] == "not_assessed"
    assert result.evidence_band == "low"
    assert all(not o.startswith("Photo visible:") for o in result.observations)
    assert any(s.startswith("photo_visible: none") for s in result.input_evidence)
    assert "would-be observation" not in _dump_text(result)
    assert not FORBIDDEN.search(_dump_text(result))


# ---------------------------------------------------------------------------
# 8. Vision unavailable -> same conservative behaviour
# ---------------------------------------------------------------------------
def test_vision_unavailable_does_not_break_crop():
    for status in ("unavailable", "stale", "error"):
        vision = _vision(status, ["should be ignored"])
        result = assess_crop(AID, _intake(symptoms=["yellowing"]), vision)
        assert result.status == "complete"
        assert result.data["vision_used"] is False
        assert result.data["vision_status"] == status
        assert result.evidence_band == "low"
        assert "should be ignored" not in _dump_text(result)
        assert not FORBIDDEN.search(_dump_text(result))


# ---------------------------------------------------------------------------
# 9. Farmer symptoms and Vision observations stay separately represented
# ---------------------------------------------------------------------------
def test_farmer_and_vision_evidence_stay_separate():
    vision = _vision("complete", ["Pale streaks along the leaf blade"])
    result = assess_crop(AID, _intake(symptoms=["yellowing", "spots"]), vision)

    farmer_lines = [o for o in result.observations if o.endswith("reported by the farmer")]
    photo_lines = [o for o in result.observations if o.startswith("Photo visible:")]
    assert len(farmer_lines) == 2
    assert len(photo_lines) == 1

    labels = result.data["evidence_labels"]
    assert labels["farmer_reported"] == [
        "visible yellowing reported by the farmer",
        "spots or blotches reported by the farmer",
    ]
    assert labels["photo_visible"] == ["Pale streaks along the leaf blade"]
    assert labels["rule_based_check"]

    assert any(s.startswith("farmer_reported:") for s in result.input_evidence)
    assert any(s.startswith("photo_visible: Pale streaks") for s in result.input_evidence)

    # Vision text is never merged into the hypothesis language.
    for cause in result.possible_causes:
        assert "Pale streaks along the leaf blade" not in cause
    # A photo line is never presented as a farmer report, and vice versa.
    assert not any("reported by the farmer" in line for line in photo_lines)
    assert not any(line.startswith("Photo visible:") for line in farmer_lines)


# ---------------------------------------------------------------------------
# 10. No pesticide/fertilizer/dose/spray/confirmed disease/irrigation command
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("overrides", SCENARIOS, ids=_sid)
def test_crop_never_emits_unsafe_output(overrides: dict):
    result = assess_crop(AID, _intake(**overrides), None)
    text = _dump_text(result)
    assert not FORBIDDEN.search(text), f"forbidden content in output: {text}"
    assert QUANTITY.search(text) is None, f"quantity + unit pattern in output: {text}"
    assert "irrigation_command" not in (result.data or {})


def test_chemical_question_is_referred_but_never_echoed():
    result = assess_crop(AID, _intake(symptoms=["yellowing"], notes="Should I spray something?"), None)
    assert result.data["referral_recommended"] is True
    assert "farmer_asked_about_chemicals" in result.data["referral_reasons"]
    text = _dump_text(result).lower()
    assert "spray" not in text  # raw question is scanned for referral, never echoed


# ---------------------------------------------------------------------------
# 11. Valid AgentResult
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("overrides", SCENARIOS, ids=_sid)
def test_crop_returns_valid_agent_result(overrides: dict):
    result = assess_crop(AID, _intake(**overrides), None)
    again = AgentResult.model_validate(result.model_dump(mode="json"))
    assert again.assessment_id == AID
    assert again.agent_id == "crop"
    assert again.provider_or_model == "deterministic-wheat-screening-rules"
    assert again.version == VERSION == "crop-rules-1.1.0"
    assert again.status in {"complete", "partial", "unsupported"}


# ---------------------------------------------------------------------------
# 12. Checks never exceed the AgentResult limit (8)
# ---------------------------------------------------------------------------
def test_crop_checks_do_not_exceed_agentresult_limit():
    # AgentResult.checks is declared with Field(max_length=8) in app/schemas.py.
    agent_result_limit = 8
    assert agent_result_limit == AgentResult.model_fields["checks"].metadata[-1].max_length
    for overrides in SCENARIOS:
        result = assess_crop(AID, _intake(**overrides), None)
        assert 1 <= len(result.checks) <= agent_result_limit
        assert len(result.observations) >= 0
        assert len(result.possible_causes) >= 1


# ---------------------------------------------------------------------------
# 13. Missing symptoms + missing Vision -> conservative result
# ---------------------------------------------------------------------------
def test_missing_symptoms_and_missing_vision_is_conservative():
    result = assess_crop(AID, _intake(symptoms=[]), None)
    assert result.status == "partial"
    assert result.evidence_band == "low"
    assert result.possible_causes == ["Cause cannot be assessed from the information provided"]
    assert result.observations == []
    assert result.data["referral_recommended"] is True
    assert "cause_remains_unknown" in result.data["referral_reasons"]
    assert "evidence_low" in result.data["referral_reasons"]
    assert "insufficient" in result.evidence_reason.lower()
    assert "safe general inspection checks" in result.evidence_reason
    assert not FORBIDDEN.search(_dump_text(result))


# ---------------------------------------------------------------------------
# 14. Sources are never fabricated; rules are explicitly marked unverified
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("overrides", SCENARIOS, ids=_sid)
def test_crop_sources_are_never_fabricated(overrides: dict):
    registry = source_registry()
    entries = {e["id"]: e for e in registry["entries"]}
    assert "crop-rules" in entries
    entry = entries["crop-rules"]
    assert entry["source_status"] == "unverified"
    assert entry["url"] is None  # no invented URL
    registry_urls = {e["url"] for e in registry["entries"] if e.get("url")}

    result = assess_crop(AID, _intake(**overrides), None)
    assert result.sources == []
    for source in result.sources:
        assert source.url in registry_urls
    text = _dump_text(result)
    assert "http://" not in text and "https://" not in text
    assert "unverified" in result.evidence_reason.lower()
    verification = result.data["rule_verification"]
    assert verification["status"] == "unverified"
    assert verification["source_registry_id"] == "crop-rules"


# ---------------------------------------------------------------------------
# Additional referral triggers: heading-to-grain stage and conflicting evidence
# ---------------------------------------------------------------------------
def test_heading_to_grain_stage_with_symptoms_refers_to_expert():
    result = assess_crop(AID, _intake(symptoms=["yellowing"], growth_stage="milk"), None)
    assert result.data["referral_recommended"] is True
    assert "heading_to_grain_stage_with_symptoms" in result.data["referral_reasons"]


def test_conflicting_evidence_refers_to_expert():
    result = assess_crop(
        AID, _intake(symptoms=["wilting"], soil_moisture="wet"), None
    )
    assert result.data["referral_recommended"] is True
    assert "evidence_conflicting" in result.data["referral_reasons"]


def test_symptom_tags_and_notes_stay_provenance_safe():
    # Free-text answer that is not a known symptom label is not echoed back.
    result = assess_crop(AID, _intake(symptoms=["some free text note"]), None)
    text = _dump_text(result)
    assert "some free text note" not in text
    assert result.status == "partial"  # no labelled evidence left
    assert not FORBIDDEN.search(text)

"""Focused tests for the Water / Crop / Farm Plan farmer-flow upgrade.

Covers the Bahawalpur wheat pilot upgrade:

- Water: the exact missing-information summary, the structured
  ``next_information_needed`` report and the ``water_summary_kind`` enum.
- Crop: deterministic symptom-aware checks, the photo-vs-farmer evidence
  split, cautious vocabulary and a hard no-diagnosis / no-product sweep.
- Farm Plan: at most three semantically de-duplicated, priority-ordered
  actions, escalation first, and no escalation for missing information alone.
- Frontend: the Urdu evidence split and the Water "what is needed next"
  panel are wired into the result UI (source level — the frontend has no
  test runner; its verification is ``tsc`` + ``vite build``).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.advisor import build_farm_plan
from app.agents.crop import assess_crop
from app.agents.water import assess_water
from app.schemas import AgentResult

AID = "44444444-4444-4444-8444-444444444444"
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"

# Grow the English list exactly like the backend does: "a", "a and b",
# "a, b, and c".
_MISSING_SENTENCE = (
    "Water guidance is limited because these field details are missing: {items}."
)
_RUST_POSSIBILITY = (
    "Rust-like leaf signs need field verification; the cause is not confirmed."
)
_DISCREPANCY_STATEMENT = (
    "The uploaded photo did not show clear visible signs, while the farmer "
    "reported symptoms. Check multiple affected plants; the photo does not "
    "rule out a field problem."
)


# --------------------------------------------------------------- helpers


def _water_intake(**overrides: Any) -> dict[str, Any]:
    """A complete, fresh Bahawalpur intake; override one field per test."""
    intake: dict[str, Any] = {
        "crop": "wheat",
        "area_code": "bahawalpur_sadar",
        "growth_stage": "tillering",
        "irrigation_history": "known",
        "last_irrigation_date": "2026-09-25",
        "soil_moisture": "moist",
        "drainage": "good",
        "soil_texture": "loamy",
        "notes": "",
    }
    intake.update(overrides)
    return intake


def _weather(
    status: str = "complete",
    freshness: str = "fresh",
) -> AgentResult:
    """A Weather envelope shaped like the connected adapter's output."""
    return AgentResult(
        assessment_id=AID,
        agent_id="weather",
        status=status,
        summary="Weather values are provider-reported forecast-grid context.",
        evidence_reason="Test weather envelope.",
        provider_or_model="test",
        version="test",
        data={
            "freshness": freshness,
            "daily_outlook": [
                {
                    "date": "2026-10-04",
                    "temperature_max_c": 33.0,
                    "temperature_min_c": 20.0,
                    "precipitation_sum_mm": 0.0,
                    "precipitation_probability_max_pct": 0,
                },
                {
                    "date": "2026-10-05",
                    "temperature_max_c": 34.0,
                    "temperature_min_c": 21.0,
                    "precipitation_sum_mm": 0.0,
                    "precipitation_probability_max_pct": 0,
                },
            ],
        },
    )


def _crop_intake(**overrides: Any) -> dict[str, Any]:
    intake: dict[str, Any] = {
        "crop": "wheat",
        "area_code": "bahawalpur_sadar",
        "growth_stage": "tillering",
        "soil_moisture": "moist",
        "drainage": "good",
        "irrigation_history": "known",
        "last_irrigation_date": "2026-09-25",
        "symptoms": [],
        "symptoms_spreading": "no",
        "notes": "",
    }
    intake.update(overrides)
    return intake


def _vision(observations: list[str], status: str = "complete") -> AgentResult:
    """A Vision card carrying only app-safe visible observations."""
    return AgentResult(
        assessment_id=AID,
        agent_id="vision",
        status=status,
        summary="Photo screening result: visible signs only, never a cause.",
        observations=list(observations),
        checks=[
            "Inspect the visible pattern on several plants in the photo and "
            "note where it starts."
        ],
        evidence_band="low",
        evidence_reason="Test vision envelope.",
        provider_or_model="self-hosted",
        version="test",
    )


def _card(
    agent_id: str,
    *,
    status: str = "complete",
    observations: list[str] | None = None,
    checks: list[str] | None = None,
    data: dict[str, Any] | None = None,
) -> AgentResult:
    """Minimal card for plan-level dedupe/ordering assertions."""
    return AgentResult(
        assessment_id=AID,
        agent_id=agent_id,
        status=status,
        summary=f"Test {agent_id} card.",
        observations=list(observations or []),
        checks=list(checks or []),
        evidence_band="low",
        evidence_reason="Test card.",
        provider_or_model="test",
        version="test",
        data=data or {},
    )


def _dump_text(value: Any) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return json.dumps(
            [item.model_dump(mode="json") for item in value],
            ensure_ascii=False,
        )
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


# ---------------------------------------------------------------- water


def test_water_names_exactly_the_missing_field_details():
    """PART A: an exact, farmer-readable missing list plus structured items."""
    result = assess_water(
        AID,
        _water_intake(
            growth_stage="not_sure",
            irrigation_history="not_sure",
            last_irrigation_date=None,
            soil_moisture="not_sure",
        ),
        _weather(),
    )

    assert result.status == "partial"
    assert result.data["missing_inputs"] == [
        "growth_stage",
        "last_irrigation_date",
        "soil_moisture",
    ]
    assert result.data["water_summary_kind"] == "information_needed"

    expected = _MISSING_SENTENCE.format(
        items="growth stage, last irrigation date, and soil moisture"
    )
    assert expected in result.summary
    # The old vague prefix is gone.
    assert "Missing inputs:" not in result.summary

    items = result.data["next_information_needed"]
    assert [item["key"] for item in items] == [
        "soil_moisture",
        "last_irrigation_date",
        "growth_stage",
    ]
    for expected_key in ("key", "label", "reason", "farmer_action", "priority"):
        assert all(expected_key in item for item in items)
    assert [item["priority"] for item in items] == [1, 2, 3]
    # A structured item is a request for information, never an irrigation order.
    assert "irrigation_command" in result.data
    assert result.data["irrigation_command"] is None


def test_water_dry_soil_reports_field_check_kind():
    result = assess_water(AID, _water_intake(soil_moisture="dry"), _weather())

    assert result.data["water_context"]["label"] == "field_check_needed"
    assert result.data["water_summary_kind"] == "field_check_needed"
    assert result.data["missing_inputs"] == []
    assert any("root depth" in check for check in result.checks)


def test_water_poor_drainage_reports_watch_drainage_kind():
    result = assess_water(AID, _water_intake(drainage="poor"), _weather())

    assert result.data["water_context"]["label"] == "watch_drainage"
    assert result.data["water_summary_kind"] == "watch_drainage"
    assert "standing water" in result.checks[0].lower()


def test_water_weather_only_gap_uses_the_fresh_forecast_sentence():
    result = assess_water(
        AID,
        _water_intake(),
        _weather(status="stale", freshness="stale_or_timestamp_missing"),
    )

    assert result.data["missing_inputs"] == ["fresh_weather_forecast"]
    assert result.data["water_summary_kind"] == "information_needed"
    assert "Water guidance is limited because there is no fresh weather forecast." in (
        result.summary
    )
    # Two or three checks, never a single one, and never an irrigation order.
    assert 2 <= len(result.checks) <= 3
    assert result.data["next_information_needed"]


# ---------------------------------------------------------------- crop


def test_crop_rust_like_evidence_uses_three_checks_and_escalation_signs():
    result = assess_crop(
        AID,
        _crop_intake(symptoms=["rust_like"], symptoms_spreading="yes"),
        None,
    )

    field_checks = result.data["field_checks"]
    assert len(field_checks) == 3
    assert len(set(field_checks)) == 3

    assert result.data["crop_possibilities"][0] == _RUST_POSSIBILITY
    assert result.data["vision_finding"] == "absent"
    assert result.data["farmer_reported_symptoms"] == [
        "rust-like marks reported by the farmer"
    ]
    assert result.data["photo_visible_findings"] == []

    assert "rust_like_pustules_reported_or_observed" in result.data["referral_reasons"]
    assert "symptoms_rapidly_spreading" in result.data["referral_reasons"]
    escalation = " ".join(result.data["escalation_signs"]).lower()
    assert "seek local expert review" in escalation

    # The referral note stays last and the three field checks precede it.
    assert result.checks[:3] == field_checks
    assert "agriculture officer" in result.checks[-1].lower()


def test_crop_yellowing_and_drying_checks_are_relevant_and_unduplicated():
    result = assess_crop(
        AID,
        _crop_intake(symptoms=["yellowing", "drying"]),
        None,
    )

    field_checks = result.data["field_checks"]
    assert 2 <= len(field_checks) <= 3
    assert len(set(field_checks)) == len(field_checks)

    joined = " ".join(field_checks).lower()
    assert "older and younger" in joined  # yellowing visual check
    assert "compare dry plants" in joined  # drying comparison check
    assert "root-zone" in joined  # shared water/soil check
    assert joined.count("older and younger") == 1
    assert "irrigat" not in joined


def test_crop_healthy_photo_states_the_farmer_photo_discrepancy():
    result = assess_crop(
        AID,
        _crop_intake(symptoms=["yellowing"]),
        _vision(["No clear visible symptoms: the leaf area shows no clear sign"]),
    )

    assert result.data["vision_finding"] == "healthy_looking"
    assert _DISCREPANCY_STATEMENT in result.data["field_checks"]
    # The statement is a check, not a cause: it is never added to the
    # photo evidence list nor phrased as a confirmation.
    assert _DISCREPANCY_STATEMENT not in result.data["photo_visible_findings"]
    assert _DISCREPANCY_STATEMENT not in result.data["crop_possibilities"]


def test_crop_unclear_photo_reports_a_photo_limitation_only():
    result = assess_crop(
        AID,
        _crop_intake(symptoms=["yellowing"]),
        _vision(["Image details unclear: the photo is too dark to read"]),
    )

    assert result.data["vision_finding"] == "unclear"
    limitations = [
        item
        for item in result.data["photo_visible_findings"]
        if item.startswith("The uploaded photo did not show readable details")
    ]
    assert len(limitations) == 1
    # A photo limitation never becomes a screening possibility.
    assert not any(
        item.startswith("The uploaded photo") for item in result.data["crop_possibilities"]
    )


# ------------------------------------------------------- safety sweep


# Affirmative claim language that must never appear in any of the three
# outputs. Negated disclaimers ("the cause is not confirmed",
# "not a probability or diagnosis") are explicitly allowed — they are the
# cautious vocabulary this upgrade requires. Every bare "confirmed" is
# checked separately below against its surrounding window.
UNSAFE_CLAIM = re.compile(
    r"\bdisease\s+(?:is\s+)?detected\b"
    r"|\btreatments?\b|\bfungicides?\b|\bpesticides?\b|\binsecticides?\b"
    r"|\bherbicides?\b|\bsprays?\b|\bsprayed\b|\bspraying\b|\bdoses?\b|\bdosage\b"
    r"|\birrigate\s+(?:now|today|immediately)\b|\bapply\s+(?:water|irrigation)\b"
    r"|\b(?:litres?|liters?)\b|\bacre-?inches?\b|\bpump\s+(?:duration|hours)\b"
    r"|کیڑے\s?مار|سپرے|کھاد|زرعی\s?دوا|دوائی|ڈوز",
    re.IGNORECASE,
)

_CONFIRMED = re.compile(r"\bconfirmed\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(?:not|never|no|cannot|can not|without|n't)\b", re.IGNORECASE)


def _assert_safe(text: str, label: str) -> None:
    match = UNSAFE_CLAIM.search(text)
    assert match is None, f"{label}: unsafe claim language {match.group(0)!r}"

    for hit in _CONFIRMED.finditer(text):
        # Provenance records of the farmer's own selection — the input-evidence
        # line "Confirmed wheat pilot area: …" and the observation
        # "Farmer-confirmed pilot area: …" — are not cause claims.
        if text[hit.start() : hit.start() + 28].lower().startswith(
            "confirmed wheat pilot area"
        ):
            continue
        if text[max(0, hit.start() - 8) : hit.start()].lower().endswith("farmer-"):
            continue
        window = text[max(0, hit.start() - 48) : hit.start()]
        assert _NEGATION.search(window), (
            f"{label}: bare confirmation claim near {text[hit.start():hit.start() + 24]!r}"
        )


def test_crop_water_and_plan_outputs_use_no_diagnosis_or_product_language():
    crop_scenarios = [
        None,
        ["yellowing"],
        ["yellowing", "drying"],
        ["rust_like"],
        ["spots"],
        ["wilting"],
        ["insects"],
        ["unknown"],
        ["lodging", "mildew_like"],
    ]
    outputs: list[tuple[str, Any]] = []

    for symptoms in crop_scenarios:
        for spreading in ("no", "yes"):
            for vision in (
                None,
                _vision(["No clear visible symptoms: nothing to read"]),
                _vision(["Rust-like marks visible; cause not confirmed: brown pustules"]),
                _vision(["Image details unclear: too dark to read"]),
            ):
                card = assess_crop(
                    AID,
                    _crop_intake(
                        symptoms=list(symptoms or []),
                        symptoms_spreading=spreading,
                    ),
                    vision,
                )
                outputs.append((f"crop {symptoms} {spreading}", card))

    water_scenarios = [
        {},
        {"soil_moisture": "dry"},
        {"soil_moisture": "not_sure"},
        {"drainage": "poor"},
        {"drainage": "waterlogging", "soil_moisture": "wet"},
        {"growth_stage": "not_sure", "irrigation_history": "not_sure"},
        {"soil_texture": "not_sure"},
    ]
    for overrides in water_scenarios:
        card = assess_water(AID, _water_intake(**overrides), _weather())
        outputs.append((f"water {overrides}", card))
    outputs.append(
        (
            "water stale forecast",
            assess_water(
                AID,
                _water_intake(),
                _weather(status="stale", freshness="stale_or_timestamp_missing"),
            ),
        )
    )

    plan_intake = _crop_intake(symptoms=["rust_like"], symptoms_spreading="yes")
    plan_cards = [
        assess_crop(AID, plan_intake, _vision(["Image details unclear: too dark"])),
        assess_water(AID, _water_intake(soil_moisture="dry"), _weather()),
        _vision(["Pale streaks along the leaf blade"]),
    ]
    outputs.append(("plan", build_farm_plan(AID, plan_intake, plan_cards)))

    for label, output in outputs:
        _assert_safe(_dump_text(output), label)


# ------------------------------------------------------------ farm plan


def test_plan_is_at_most_three_ordered_deduplicated_actions():
    crop = assess_crop(AID, _crop_intake(symptoms=["yellowing", "drying"]), None)
    water = assess_water(AID, _water_intake(soil_moisture="dry"), _weather())
    vision = _vision(["Pale streaks along the leaf blade"])

    plan = build_farm_plan(
        AID,
        _crop_intake(symptoms=["yellowing", "drying"]),
        [crop, water, vision],
    )

    assert plan.status == "field_inspection_recommended"
    assert 1 <= len(plan.checks) <= 3
    assert [check.priority for check in plan.checks] == list(
        range(1, len(plan.checks) + 1)
    )

    titles = [check.title for check in plan.checks]
    assert len({title.casefold() for title in titles}) == len(titles)
    assert plan.checks[0].evidence_labels == ["crop"]

    for check in plan.checks:
        assert check.title and check.how_to_check and check.why and check.what_to_observe
        assert check.evidence_labels
        assert check.evidence_labels[0] in {"crop", "water", "vision"}
    _assert_safe(_dump_text(plan), "plan")


def test_plan_merges_semantically_equivalent_checks():
    """Same theme from Crop and Water collapses into one action."""
    crop = _card(
        "crop",
        observations=["visible yellowing reported by the farmer"],
        checks=[
            "Check root-zone soil moisture by hand in affected and "
            "healthy-looking spots."
        ],
    )
    water = _card(
        "water",
        observations=["Farmer-reported field context is complete."],
        checks=[
            "Check root-zone soil moisture and drainage before attributing a cause."
        ],
    )
    vision = _vision(["Pale streaks along the leaf blade"])

    plan = build_farm_plan(AID, _crop_intake(), [crop, water, vision])

    titles = [check.title.casefold() for check in plan.checks]
    assert len(plan.checks) <= 3
    root_zone_actions = [
        title for title in titles if "root-zone" in title or "moisture" in title
    ]
    assert len(root_zone_actions) == 1
    assert titles[0].startswith("check root-zone soil moisture by hand")
    assert len(set(titles)) == len(titles)


def test_plan_escalates_first_only_when_real_criteria_exist():
    intake = _crop_intake(symptoms=["rust_like"], symptoms_spreading="yes")
    crop = assess_crop(AID, intake, None)
    water = assess_water(AID, _water_intake(), _weather())

    plan = build_farm_plan(AID, intake, [crop, water])

    assert plan.status == "expert_review_recommended"
    assert plan.checks[0].title == crop.data["escalation_signs"][0]
    assert plan.checks[0].evidence_labels == ["crop"]

    escalation_actions = [
        check
        for check in plan.checks
        if "agriculture officer" in check.title.casefold()
        or "expert review" in check.title.casefold()
    ]
    assert len(escalation_actions) == 1
    assert plan.checks.index(escalation_actions[0]) == 0


def test_plan_does_not_escalate_for_missing_information_alone():
    crop = assess_crop(AID, _crop_intake(symptoms=["yellowing"]), None)
    water = assess_water(AID, _water_intake(), _weather())

    # The card is referred only because information is thin — no real
    # escalation criterion exists.
    assert crop.data["referral_recommended"] is True
    assert set(crop.data["referral_reasons"]) <= {
        "cause_remains_unknown",
        "evidence_low",
    }

    plan = build_farm_plan(
        AID,
        _crop_intake(symptoms=["yellowing"]),
        [crop, water],
    )

    assert plan.status != "expert_review_recommended"
    assert plan.status == "field_inspection_recommended"
    assert not any(
        "seek local expert review" in check.title.casefold()
        for check in plan.checks
    )


# ------------------------------------------------------------ frontend


def test_frontend_ships_the_urdu_evidence_split_and_next_information_panels():
    """PART D: the structured panels, their EN/UR labels and the collapsed
    technical details are present in the shipped sources."""
    panels = (FRONTEND_SRC / "components" / "ResultPanels.tsx").read_text(
        encoding="utf-8"
    )
    card = (FRONTEND_SRC / "components" / "AgentCard.tsx").read_text(encoding="utf-8")
    en = (FRONTEND_SRC / "i18n" / "en.ts").read_text(encoding="utf-8")
    ur = (FRONTEND_SRC / "i18n" / "ur.ts").read_text(encoding="utf-8")
    backend_text = (FRONTEND_SRC / "i18n" / "backendText.ts").read_text(
        encoding="utf-8"
    )

    # --- Crop evidence split, five sections -------------------------------
    for key in (
        "crop.evidence.heading",
        "crop.evidence.farmer",
        "crop.evidence.photo",
        "crop.evidence.possibilities",
        "crop.evidence.checks",
        "crop.evidence.escalation",
    ):
        assert f'"{key}"' in en, f"missing EN key {key}"
        assert f'"{key}"' in ur, f"missing UR key {key}"

    for urdu_label in (
        "کسان کی بتائی ہوئی علامات",
        "تصویر میں نظر آنے والی علامات",
        "جانچ کے امکانات",
        "کھیت میں جانچ",
        "ماہر سے رابطے کی علامات",
    ):
        assert urdu_label in ur, f"missing Urdu label {urdu_label}"

    assert "CropEvidencePanel" in panels
    assert "CropEvidencePanel" in card
    for field in (
        "farmer_reported_symptoms",
        "photo_visible_findings",
        "crop_possibilities",
        "field_checks",
        "escalation_signs",
    ):
        assert field in panels, f"panel does not read data.{field}"

    # --- Water "what is needed next" --------------------------------------
    assert '"water.next.heading": "What is needed next"' in en
    assert '"water.next.infoNeeded": "مزید درکار معلومات"' in ur
    assert '"water.next.fieldCheck": "کھیت میں اگلی جانچ"' in ur
    assert '"water.next.label.soil_moisture": "مٹی کی نمی"' in ur
    assert "WaterNextInformation" in panels
    assert "WaterNextInformation" in card
    assert "next_information_needed" in panels

    # --- Collapsed technical details --------------------------------------
    assert '"agent.technicalDetails": "Technical details"' in en
    assert '"agent.technicalDetails": "تکنیکی تفصیلات"' in ur
    assert "agent-details--technical" in card

    # --- Fixed backend messages are localized, EN and UR ------------------
    for fixed in (
        _RUST_POSSIBILITY,
        "Check root-zone soil moisture, drainage, and roots before attributing a cause.",
        "Check for standing water, blocked outlets, and whether the soil remains "
        "saturated after irrigation/rain.",
        "Ask a local agriculture officer or qualified expert to review these signs "
        "before any action.",
        "Share what you recorded with a local agriculture officer or qualified "
        "expert and follow their guidance.",
    ):
        assert fixed in backend_text, f"unmapped fixed message: {fixed}"

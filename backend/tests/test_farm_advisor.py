"""Tests for the hardened, deterministic Farm Advisor.

Covers the status ladder, referral gating (only assessed cards may escalate),
conflict surfacing (moisture vs crop signs, moisture vs weather, weather
freshness, crop vs vision), check prioritization/dedup/cap, the defensive
unsafe-language filter, the permanent safety banner, and FarmPlan schema
validity.
"""

from __future__ import annotations

import json
from uuid import uuid4

from app.agents.advisor import SAFETY_BANNER, build_farm_plan
from app.core.text_guard import find_unsafe
from app.schemas import AgentResult, FarmPlan

AID = str(uuid4())
STATUSES = {
    "insufficient_information",
    "monitor",
    "field_inspection_recommended",
    "expert_review_recommended",
}


def _card(
    agent_id,
    status="complete",
    summary=None,
    observations=(),
    possible_causes=(),
    checks=(),
    data=None,
) -> AgentResult:
    return AgentResult(
        assessment_id=AID,
        agent_id=agent_id,
        status=status,
        summary=summary or f"{agent_id.title()} card summary.",
        observations=list(observations),
        possible_causes=list(possible_causes),
        checks=list(checks),
        evidence_reason="Evidence is limited; test envelope.",
        provider_or_model="test",
        version="test",
        data=dict(data or {}),
    )


def _intake(**overrides) -> dict:
    base = {
        "crop": "wheat",
        "growth_stage": "tillering",
        "irrigation_history": "known",
        "symptoms": ["yellowing"],
        "symptoms_spreading": "not_sure",
        "soil_moisture": "moist",
    }
    base.update(overrides)
    return base


def _plan(intake: dict, *cards: AgentResult) -> FarmPlan:
    return build_farm_plan(AID, intake, list(cards))


def _topics(plan: FarmPlan) -> list[str]:
    return [conflict["topic"] for conflict in plan.conflicts]


# ---------------------------------------------------------------- 1. ladder
def test_all_agents_complete_produces_field_inspection_plan():
    plan = _plan(
        _intake(),
        _card(
            "crop",
            observations=["Farmer reported yellowing on lower leaves"],
            checks=["Compare older and younger leaves and note where the change starts"],
        ),
        _card(
            "water",
            checks=["Check soil moisture by hand at root depth"],
            data={"water_attention": "inspect_field"},
        ),
        _card(
            "vision",
            observations=["Yellowing: lower leaves yellowing"],
            checks=["Compare the visible pattern on several plants"],
        ),
        _card("weather", data={"freshness": "fresh", "current": {"precipitation_mm": 0}}),
        _card("market", summary="Price unavailable: no verified quote was supplied."),
    )
    assert plan.status == "field_inspection_recommended"
    # Priority order crop -> water -> vision.
    assert [check.evidence_labels[0] for check in plan.checks] == ["crop", "water", "vision"]
    # Fresh, consistent evidence produces no spurious conflicts.
    assert plan.conflicts == []


# ------------------------------------------------------- 2. referral flags
def test_crop_referral_flag_escalates_to_expert_review():
    plan = _plan(
        _intake(),
        _card(
            "crop",
            observations=["Yellowing noted on lower leaves"],
            checks=["Compare older and younger leaves"],
            data={"referral_recommended": True, "referral_reasons": ["severe_spreading"]},
        ),
    )
    assert plan.status == "expert_review_recommended"


def test_water_expert_review_attention_escalates():
    plan = _plan(
        _intake(),
        _card(
            "water",
            checks=["Check soil moisture by hand at root depth"],
            data={"water_attention": "expert_review"},
        ),
    )
    assert plan.status == "expert_review_recommended"


# ------------------------------------------------- 3. water insufficient
def test_water_insufficient_information_downgrades_the_plan():
    plan = _plan(
        _intake(),
        _card(
            "water",
            checks=["Check soil moisture by hand at root depth"],
            data={"water_attention": "insufficient_information"},
        ),
    )
    assert plan.status == "insufficient_information"

    # The declared ladder keeps insufficient_information above inspection.
    plan2 = _plan(
        _intake(),
        _card("crop", observations=["Farmer reported yellowing"], checks=["Compare older and younger leaves"]),
        _card(
            "water",
            checks=["Check soil moisture by hand"],
            data={"water_attention": "insufficient_information"},
        ),
    )
    assert plan2.status == "insufficient_information"


# ------------------------------------------------- 4. vision not_assessed
def test_vision_not_assessed_does_not_block_the_plan():
    plan = _plan(
        _intake(),
        _card(
            "crop",
            observations=["Farmer reported yellowing on lower leaves"],
            checks=["Compare older and younger leaves"],
        ),
        _card("water", checks=["Check soil moisture by hand"], data={"water_attention": "monitor"}),
        _card("vision", status="not_assessed", summary="Vision was not assessed because no photo was supplied."),
    )
    assert plan.status == "field_inspection_recommended"
    assert not any(check.evidence_labels == ["vision"] for check in plan.checks)
    # The abstaining card is still disclosed, not hidden.
    assert plan.agent_summary["vision"] == "Vision was not assessed because no photo was supplied."


# -------------------------------------------------- 5. market unavailable
def test_market_unavailable_does_not_block_the_plan():
    cards = (
        _card("crop", observations=["Farmer reported yellowing"], checks=["Compare older and younger leaves"]),
        _card("water", checks=["Check soil moisture by hand"], data={"water_attention": "monitor"}),
    )
    with_market = _plan(_intake(), *cards, _card("market", status="unavailable", summary="Price unavailable."))
    without_market = _plan(_intake(), *cards)
    assert with_market.status == without_market.status == "field_inspection_recommended"
    assert "market" in with_market.agent_summary
    assert "market" not in without_market.agent_summary


# --------------------------------------------------- 6. weather conflict
def test_stale_weather_conflict_is_preserved():
    plan = _plan(
        _intake(),
        _card("crop", observations=["Farmer reported yellowing"], checks=["Compare older and younger leaves"]),
        _card("weather", status="stale", data={"freshness": "stale_or_timestamp_missing"}),
    )
    assert "weather_freshness" in _topics(plan)
    freshness = next(c for c in plan.conflicts if c["topic"] == "weather_freshness")
    assert "Do not use this weather result" in freshness["next_check"]
    # Stale weather never becomes an affirmative input to the ladder.
    assert plan.status == "field_inspection_recommended"


# ------------------------------------------------------------ 7. max 3
def test_checks_are_capped_at_three():
    plan = _plan(
        _intake(),
        _card("crop", observations=["Yellowing"], checks=[f"Compare crop check number {n} on several plants" for n in range(8)]),
        _card("water", checks=[f"Water check number {n} by hand" for n in range(4)], data={"water_attention": "inspect_field"}),
        _card("vision", observations=["Yellowing present"], checks=[f"Vision check number {n}" for n in range(3)]),
    )
    assert len(plan.checks) == 3
    assert [check.priority for check in plan.checks] == [1, 2, 3]
    assert [check.id for check in plan.checks] == ["check-1", "check-2", "check-3"]


# ----------------------------------------------------------- 8. dedup
def test_duplicate_checks_are_deduplicated():
    shared = "Compare the affected patch with a healthy-looking area"
    plan = _plan(
        _intake(),
        _card("crop", observations=["Farmer reported spots"], checks=[shared, "Mark the edge of the affected patch"]),
        _card("water", checks=[shared, "Check soil moisture by hand"], data={"water_attention": "inspect_field"}),
        _card("vision", observations=["Spots visible"], checks=[shared]),
    )
    titles = [check.title for check in plan.checks]
    assert titles.count(shared) == 1
    assert len(titles) == len({title.casefold() for title in titles})
    assert len(titles) <= 3


# ------------------------------------------------ 9. no unsafe language
def _sample_plans() -> list[FarmPlan]:
    return [
        _plan(
            _intake(),
            _card("crop", observations=["Farmer reported yellowing"], checks=["Compare older and younger leaves"]),
            _card("water", checks=["Check soil moisture by hand"], data={"water_attention": "inspect_field"}),
        ),
        _plan(_intake(symptoms_spreading="yes"), _card("crop", observations=["Yellowing"], checks=["Mark the edge of the affected patch"])),
        _plan(_intake(soil_moisture="wet"), _card("crop", observations=["Farmer reported wilting and water stress"], checks=["Check whether leaves are rolling"])),
        _plan(_intake(growth_stage="not_sure", irrigation_history="not_sure", symptoms=[])),
        _plan(_intake(soil_moisture="dry"), _card("weather", data={"freshness": "fresh", "current": {"precipitation_mm": 7.5}})),
        _plan(_intake(), _card("water", checks=["Check soil moisture by hand"], data={"water_attention": "insufficient_information"})),
        _plan(_intake(), _card("vision", status="not_assessed", summary="No photo supplied.")),
        _plan(
            _intake(),
            _card(
                "crop",
                observations=["Farmer reported wilting of the whole plant"],
                checks=["Check whether leaves are rolling"],
            ),
            _card(
                "vision",
                observations=["Visible insects: aphids observed on the stem"],
                checks=["Compare the visible pattern on several plants"],
            ),
        ),
    ]


def test_no_unsafe_language_anywhere_in_the_plan():
    for plan in _sample_plans():
        text = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False)
        assert find_unsafe(text) == [], text
        lowered = text.casefold()
        for token in ("irrigate now", "pesticide", "fertilizer", "buy now", "price prediction", "guaranteed"):
            assert token not in lowered, (token, text)


# --------------------------------------------------------- 10. banner
def test_safety_banner_always_present():
    for plan in _sample_plans():
        assert plan.safety_banner
        assert plan.safety_banner == SAFETY_BANNER
        assert "not a confirmed diagnosis" in plan.safety_banner.lower()


# --------------------------------------------------------- 11. schema
def test_farm_plan_round_trips_through_schema():
    plan = _plan(
        _intake(),
        _card("crop", observations=["Farmer reported yellowing"], checks=["Compare older and younger leaves"]),
        _card("water", checks=["Check soil moisture by hand"], data={"water_attention": "inspect_field"}),
        _card("vision", observations=["Yellowing present"], checks=["Compare the visible pattern"]),
    )
    validated = FarmPlan.model_validate(plan.model_dump(mode="json"))
    assert validated.status in STATUSES
    assert set(validated.agent_summary) <= {"weather", "water", "crop", "vision", "market"}
    assert validated.verification_step
    assert validated.policy_version
    assert validated.safety_banner
    assert 1 <= len(validated.checks) <= 3
    for check in validated.checks:
        assert check.title
        assert check.how_to_check and check.how_to_check != check.title  # distinct how
        assert check.why
        assert check.what_to_observe
        assert check.evidence_labels
        assert 1 <= check.priority <= 3


# ------------------------------------------------- extra: A4 failed cards
def test_failed_cards_never_contribute_or_escalate():
    plan = _plan(
        _intake(),
        _card("crop", status="unavailable", observations=[], data={"referral_recommended": True}),
    )
    assert plan.status != "expert_review_recommended"
    assert plan.status == "monitor"

    stale_vision = _plan(
        _intake(),
        _card("vision", status="stale", observations=["Yellowing"], checks=["Compare the visible pattern"]),
    )
    assert not any(check.evidence_labels == ["vision"] for check in stale_vision.checks)

    errored_water = _plan(
        _intake(),
        _card("water", status="error", checks=["Check soil moisture by hand"], data={"water_attention": "expert_review"}),
    )
    assert errored_water.status != "expert_review_recommended"


# ------------------------------------------ extra: defensive unsafe filter
def test_unsafe_agent_check_text_is_filtered_out():
    plan = _plan(
        _intake(),
        _card(
            "crop",
            observations=["Farmer reported yellowing"],
            checks=[
                "Spray pesticide at the first sign of yellowing",
                "Compare older and younger leaves on several plants",
            ],
        ),
    )
    assert all("pesticide" not in check.title.casefold() for check in plan.checks)
    assert any("Compare older and younger leaves" in check.title for check in plan.checks)

    all_unsafe = _plan(
        _intake(),
        _card("crop", observations=["Yellowing"], checks=["Dose with urea immediately"]),
    )
    assert all_unsafe.checks[0].title.startswith("Describe which plant part")
    assert all_unsafe.checks[0].evidence_labels == ["farmer_reported"]


# ------------------------------------------ extra: crop vs vision conflict
def test_crop_vision_disagreement_is_surfaced_without_consensus():
    plan = _plan(
        _intake(),
        _card("crop", observations=["Farmer reported wilting of the whole plant"], checks=["Check whether leaves are rolling"]),
        _card("vision", observations=["Visible insects: aphids observed on the stem"], checks=["Compare the visible pattern"]),
    )
    assert "crop_vision_disagreement" in _topics(plan)
    conflict = next(c for c in plan.conflicts if c["topic"] == "crop_vision_disagreement")
    assert conflict["findings"][0].startswith("Crop Agent evidence:")
    assert conflict["findings"][1].startswith("Vision Agent visible signs:")
    assert conflict["next_check"]
    # Both sides stay visible; the plan still returns (no forced consensus).
    assert plan.status == "field_inspection_recommended"

    agreeing = _plan(
        _intake(),
        _card("crop", observations=["Farmer reported yellowing on lower leaves"], checks=["Compare older and younger leaves"]),
        _card("vision", observations=["Yellowing: lower leaves yellowing"], checks=["Compare the visible pattern"]),
    )
    assert "crop_vision_disagreement" not in _topics(agreeing)


# ------------------------------------------ extra: moisture vs weather
def test_field_moisture_vs_weather_conflict():
    plan = _plan(
        _intake(soil_moisture="dry"),
        _card("crop", observations=["Farmer reported yellowing"], checks=["Compare older and younger leaves"]),
        _card("weather", data={"freshness": "fresh", "current": {"precipitation_mm": 4.5}}),
    )
    assert "field_moisture_vs_weather" in _topics(plan)
    conflict = next(c for c in plan.conflicts if c["topic"] == "field_moisture_vs_weather")
    assert "4.5 mm" in conflict["findings"][1]

    # No rain recorded -> no conflict.
    no_rain = _plan(_intake(soil_moisture="dry"), _card("weather", data={"freshness": "fresh", "current": {"precipitation_mm": 0}}))
    assert "field_moisture_vs_weather" not in _topics(no_rain)

    # Moist soil + rain is consistent -> no conflict.
    moist = _plan(_intake(soil_moisture="moist"), _card("weather", data={"freshness": "fresh", "current": {"precipitation_mm": 4.5}}))
    assert "field_moisture_vs_weather" not in _topics(moist)

    # Stale weather data is never used for this conflict.
    stale = _plan(_intake(soil_moisture="dry"), _card("weather", status="stale", data={"current": {"precipitation_mm": 4.5}}))
    assert "field_moisture_vs_weather" not in _topics(stale)


# ------------------------------------------ extra: moisture vs crop signs
def test_field_moisture_vs_crop_conflict_preserved():
    plan = _plan(
        _intake(soil_moisture="wet"),
        _card("crop", observations=["Farmer reported wilting and water stress in patches"], checks=["Check whether leaves are rolling"]),
    )
    assert "field_moisture" in _topics(plan)


# --------------------------------------------------- extra: ladder priority
def test_referral_outranks_insufficient_information():
    plan = _plan(
        _intake(symptoms_spreading="yes"),
        _card("water", checks=["Check soil moisture by hand"], data={"water_attention": "insufficient_information"}),
    )
    assert plan.status == "expert_review_recommended"


# ------------------------------------------------- extra: fallback path
def test_unknown_context_falls_back_to_insufficient_with_generic_check():
    plan = _plan(_intake(growth_stage="not_sure", irrigation_history="not_sure", symptoms=[]))
    assert plan.status == "insufficient_information"
    assert len(plan.checks) == 1
    assert plan.checks[0].evidence_labels == ["farmer_reported"]
    assert plan.checks[0].what_to_observe

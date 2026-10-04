from __future__ import annotations

import uuid

from agents.water.agent import analyze_water, evaluate_water, get_water_attention
from agents.water.schema import validate_output
from backend.app.agents.water import assess_water

NOW = "2026-10-04T00:00:00Z"


def fresh_weather(*, rain: bool = True, status: str = "fresh"):
    hourly = [
        {
            "time": "2026-10-04T12:00:00+05:00",
            "precipitation_mm": 0.0,
            "precipitation_probability_pct": 20.0 if rain else 0.0,
        }
    ]
    daily = [
        {
            "date": "2026-10-04",
            "precipitation_sum_mm": 0.0,
            "precipitation_probability_max_pct": 20.0 if rain else 0.0,
        }
    ]
    return {
        "assessment_id": str(uuid.uuid4()),
        "agent_id": "weather",
        "status": "complete" if status == "fresh" else "stale",
        "summary": "Weather products remain separate.",
        "sources": [
            {
                "title": "Open-Meteo Forecast API documentation",
                "url": "https://open-meteo.com/en/docs",
                "publisher": "Open-Meteo",
                "retrieved_at": NOW,
                "source_status": "official",
            }
        ],
        "data": {
            "weather_status": "weather_fresh" if status == "fresh" else "weather_stale",
            "providers": {
                "open_meteo": {
                    "hourly_72h": {
                        "status": status,
                        "weather_status": f"weather_{status}",
                        "retrieved_at": NOW,
                        "values": hourly,
                    },
                    "daily_7d": {
                        "status": status,
                        "weather_status": f"weather_{status}",
                        "retrieved_at": NOW,
                        "values": daily,
                    },
                }
            },
        },
    }


def complete_intake(**overrides):
    value = {
        "crop": "wheat",
        "area_code": "bahawalpur_sadar",
        "growth_stage": "tillering",
        "irrigation_history": "known",
        "last_irrigation_date": "2026-09-28",
        "sowing_date": "2026-09-15",
        "soil_texture": "loamy",
        "soil_moisture": "moist",
        "drainage": "good",
    }
    value.update(overrides)
    return value


def test_standalone_output_matches_required_common_agent_envelope():
    result = analyze_water(
        crop="wheat",
        area="bahawalpur_sadar",
        growth_stage="tillering",
        irrigation_history="known",
        last_irrigation_date="2026-09-28",
        sowing_date="2026-09-15",
        soil_texture="loamy",
        days_after_sowing=48,
        soil_moisture="moist",
        drainage="good",
        weather=fresh_weather(),
    )
    expected = {
        "agent_id",
        "assessment_id",
        "status",
        "summary",
        "observations",
        "possible_causes",
        "checks",
        "evidence_band",
        "evidence_reason",
        "sources",
        "provider_or_model",
        "version",
        "created_at",
        "safety_flags",
    }
    assert set(result) == expected
    assert result["agent_id"] == "water"
    assert result["status"] == "complete"
    assert get_water_attention(result) == "recheck_after_rain"
    assert result["checks"]
    assert "weather" in " ".join(result["observations"]).lower()
    assert any("soil texture: loamy" in item for item in result["observations"])
    assert any(
        "sowing-date or das context" in item.lower() for item in result["observations"]
    )
    assert validate_output(result) == []


def test_rain_prompt_only_after_actual_rain_and_with_known_good_drainage():
    result = evaluate_water(complete_intake(), weather=fresh_weather(rain=True))
    assert result["backend_data"]["water_attention"] == "recheck_after_rain"
    assert result["backend_data"]["water_context"]["rain_recheck_eligible"] is True
    assert (
        result["backend_data"]["water_context"][
            "maximum_hourly_precipitation_probability_pct"
        ]
        == 20.0
    )
    assert (
        result["backend_data"]["water_context"]["used_for_numeric_thresholds"] is False
    )
    assert result["backend_data"]["irrigation_command"] is None
    assert any(
        "after rainfall is actually observed" in check.lower()
        for check in result["checks"]
    )


def test_wet_soil_or_poor_drainage_blocks_rain_recheck():
    for overrides in (
        {"soil_moisture": "wet"},
        {"drainage": "poor"},
        {"drainage": "waterlogging"},
    ):
        result = evaluate_water(
            complete_intake(**overrides), weather=fresh_weather(rain=True)
        )
        assert result["backend_data"]["water_attention"] == "inspect_field"
        assert result["backend_data"]["water_context"]["rain_recheck_eligible"] is False
        assert "drainage_or_saturation_inspection" in result["safety_flags"]


def test_unknown_context_and_stale_weather_abstain_from_rain_prompt():
    unknown = evaluate_water(
        {"crop": "wheat", "area_code": "bahawalpur_sadar", "growth_stage": "not_sure"},
        weather=fresh_weather(rain=True),
    )
    assert unknown["backend_data"]["water_attention"] == "insufficient_information"
    stale = evaluate_water(
        complete_intake(), weather=fresh_weather(rain=True, status="stale")
    )
    assert stale["backend_data"]["water_attention"] == "insufficient_information"
    assert stale["backend_data"]["water_context"]["status"] == "stale"
    assert (
        stale["backend_data"]["water_context"]["precipitation_forecast_present"] is None
    )
    assert stale["sources"] == []


def test_cri_is_an_inspection_cue_not_a_schedule():
    result = evaluate_water(
        complete_intake(growth_stage="cri"), weather=fresh_weather(rain=False)
    )
    assert result["backend_data"]["water_attention"] == "inspect_field"
    assert "no regional schedule" in result["summary"].lower()
    assert result["backend_data"]["irrigation_command"] is None


def test_legacy_day_counts_and_das_do_not_affect_water_decision():
    a = analyze_water(
        crop="wheat",
        area="bahawalpur_sadar",
        last_irrigation_days=1,
        days_after_sowing=25,
        growth_stage="tillering",
        irrigation_history="known",
        last_irrigation_date="2026-09-28",
        soil_moisture="moist",
        drainage="good",
        weather=fresh_weather(rain=False),
    )
    b = analyze_water(
        crop="wheat",
        area="bahawalpur_sadar",
        last_irrigation_days=99,
        days_after_sowing=180,
        growth_stage="tillering",
        irrigation_history="known",
        last_irrigation_date="2026-09-28",
        soil_moisture="moist",
        drainage="good",
        weather=fresh_weather(rain=False),
    )
    assert get_water_attention(a) == get_water_attention(b) == "monitor"


def test_backend_adapter_returns_typed_agent_result_with_weather_data():
    result = assess_water(
        str(uuid.uuid4()),
        complete_intake(),
        weather=fresh_weather(rain=True),
    )
    assert result.agent_id == "water"
    assert result.status == "complete"
    assert result.data["water_attention"] == "recheck_after_rain"
    assert result.data["irrigation_command"] is None
    assert result.data["water_context"]["provider"] == "Open-Meteo"
    assert result.sources and result.sources[0].publisher == "Open-Meteo"
    assert all("irrigate now" not in check.lower() for check in result.checks)


def test_unsupported_scope_is_unavailable_without_fallback():
    result = analyze_water(crop="rice", area="multan")
    assert result["status"] == "unavailable"
    assert result["agent_id"] == "water"
    assert validate_output(result) == []

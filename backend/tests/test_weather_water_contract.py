"""Weather <-> Water contract tests for the connected backend.

Covers:
- the shared normalization module (app.services.weather_panel) that converts
  the connected Weather adapter output into the Water v2.0.0 panel shape,
- Water v2.0.0 behavior through the backend adapter (app.agents.water):
  fresh weather is usable, stale/missing weather stays conservative, rain
  only yields recheck_after_rain without drainage/waterlogging risk, and
  the agent never returns an irrigation command or unsafe language.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.agents.water import assess_water
from app.schemas import AgentResult, Source
from app.services.weather_panel import normalize_weather_for_water
from app.team_agents.water.schema import find_unsafe

ASSESSMENT_ID = "00000000-0000-4000-8000-000000000007"

ALLOWED_ATTENTION_STATES = {
    "inspect_field",
    "monitor",
    "recheck_after_rain",
    "insufficient_information",
    "expert_review",
}

ALLOWED_WATER_STATUSES = {
    "complete",
    "partial",
    "unavailable",
    "stale",
    "not_assessed",
    "unsupported",
    "error",
}


def _intake(**overrides):
    base = {
        "crop": "wheat",
        "area_code": "bahawalpur_sadar",
        "growth_stage": "tillering",
        "irrigation_history": "known",
        "last_irrigation_date": "2026-09-25",
        "soil_moisture": "moist",
        "drainage": "good",
        "soil_texture": "loamy",
    }
    base.update(overrides)
    return base


def _dry_days():
    return [
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
    ]


def _rainy_days():
    return [
        {
            "date": "2026-10-04",
            "temperature_max_c": 31.0,
            "temperature_min_c": 20.0,
            "precipitation_sum_mm": 12.0,
            "precipitation_probability_max_pct": 80,
        },
        {
            "date": "2026-10-05",
            "temperature_max_c": 29.0,
            "temperature_min_c": 19.0,
            "precipitation_sum_mm": 0.0,
            "precipitation_probability_max_pct": 0,
        },
    ]


def _weather(
    status="complete",
    freshness="fresh",
    daily=None,
    with_sources=True,
):
    """A Weather AgentResult shaped exactly like the connected adapter emits."""
    now = datetime.now(UTC)
    sources = []
    if with_sources:
        sources = [
            Source(
                title="Open-Meteo forecast API",
                url="https://open-meteo.com/en/docs",
                publisher="Open-Meteo",
                geography="Forecast grid near selected Bahawalpur area",
                retrieved_at=now,
                source_status="official",
            )
        ]

    return AgentResult(
        assessment_id=ASSESSMENT_ID,
        agent_id="weather",
        status=status,
        summary="Weather values are provider-reported forecast-grid context, not field measurements.",
        evidence_reason="Test weather envelope.",
        provider_or_model="open-meteo",
        version="test",
        created_at=now,
        sources=sources,
        data={
            "location_name": "Bahawalpur Sadar",
            "timezone": "Asia/Karachi",
            "provider_observation_at": now.isoformat(),
            "retrieved_at": now.isoformat(),
            "freshness": freshness,
            "current": {
                "temperature_c": 33.0,
                "relative_humidity_pct": 40.0,
                "precipitation_mm": 0.0,
                "wind_speed_kmh": 12.0,
                "weather_code": 1,
            },
            "daily_outlook": _dry_days() if daily is None else daily,
        },
    )


def _assert_never_irrigates(result):
    """PRD invariants for every Water card, whatever the weather did."""
    assert result.status in ALLOWED_WATER_STATUSES
    assert result.data.get("irrigation_command") is None
    assert result.data.get("water_attention") in ALLOWED_ATTENTION_STATES

    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    lowered = dumped.lower()
    assert "irrigate now" not in lowered
    # Legacy v1.0 verdict prefix must never come back.
    assert "irrigation status:" not in lowered
    # No pesticide, fertilizer, dose or spray language anywhere in the card.
    assert find_unsafe(dumped) is None


# --------------------------------------------------------------------------
# B. Weather -> Water normalization
# --------------------------------------------------------------------------


def test_normalization_maps_adapter_output_to_water_panels():
    panel = normalize_weather_for_water(_weather())

    providers = panel["data"]["providers"]["open_meteo"]
    daily = providers["daily_7d"]
    hourly = providers["hourly_72h"]

    assert panel["status"] == "fresh"
    assert daily["status"] == "fresh"
    # Daily rows are copied from data.daily_outlook - not invented.
    assert daily["values"] == _dry_days()
    # The connected adapter exposes no hourly series; none is fabricated.
    assert hourly["status"] == "unavailable"
    assert hourly["values"] == []

    # data.current / data.freshness / data.daily_outlook are mapped through.
    assert panel["data"]["current"]["temperature_c"] == 33.0
    assert panel["data"]["freshness"] == "fresh"
    assert panel["data"]["daily_outlook"] == _dry_days()

    # weather.sources become Water source records with usable timestamps.
    assert panel["sources"][0]["publisher"] == "Open-Meteo"
    assert panel["sources"][0]["url"].startswith("https://")
    assert panel["sources"][0]["retrieved_at"]


def test_normalization_refuses_to_upgrade_stale_or_missing_weather():
    stale = normalize_weather_for_water(
        _weather(status="stale", freshness="stale_or_timestamp_missing")
    )
    assert stale["status"] == "stale"
    assert stale["data"]["providers"]["open_meteo"]["daily_7d"]["status"] == "stale"

    unavailable = normalize_weather_for_water(
        _weather(status="unavailable", freshness="unavailable", with_sources=False)
    )
    assert unavailable["status"] == "unavailable"

    absent = normalize_weather_for_water(None)
    assert absent["status"] == "unavailable"
    assert absent["data"]["providers"]["open_meteo"]["daily_7d"]["values"] == []
    assert absent["sources"] == []


# --------------------------------------------------------------------------
# B6. Water behavior driven by the normalized weather context
# --------------------------------------------------------------------------


def test_fresh_complete_weather_produces_a_usable_water_context():
    result = assess_water(ASSESSMENT_ID, _intake(), _weather())

    assert result.status == "complete"
    context = result.data["water_context"]
    assert context["status"] == "fresh"
    assert context["weather_product_statuses"]["daily_7d"] == "fresh"
    assert context["used_for_numeric_thresholds"] is False
    assert context["rain_recheck_eligible"] is False
    assert result.data["water_attention"] == "monitor"
    # Fresh weather provenance flows onto the Water card.
    assert result.sources and result.sources[0].publisher == "Open-Meteo"
    _assert_never_irrigates(result)


def test_stale_weather_produces_a_conservative_water_result():
    stale = _weather(status="stale", freshness="stale_or_timestamp_missing")
    result = assess_water(ASSESSMENT_ID, _intake(), stale)

    assert result.status == "partial"
    assert result.data["water_attention"] == "insufficient_information"
    assert result.data["water_context"]["status"] == "stale"
    assert "weather_not_used_or_not_fresh" in result.safety_flags
    assert result.data["water_context"]["used_for_numeric_thresholds"] is False
    _assert_never_irrigates(result)


def test_missing_weather_produces_information_gap_never_an_irrigation_command():
    # 1. No weather envelope at all, complete field context.
    result = assess_water(ASSESSMENT_ID, _intake(), None)
    assert result.status == "partial"
    assert result.data["water_attention"] == "insufficient_information"
    assert result.data["water_context"]["status"] == "unavailable"
    _assert_never_irrigates(result)

    # 2. Explicitly unavailable weather envelope.
    offline = _weather(
        status="unavailable", freshness="unavailable", with_sources=False
    )
    result = assess_water(ASSESSMENT_ID, _intake(), offline)
    assert result.status == "partial"
    assert result.data["water_attention"] == "insufficient_information"
    assert result.data["water_context"]["status"] == "unavailable"
    _assert_never_irrigates(result)

    # 3. No weather and mostly unknown field context.
    unknown = _intake(
        growth_stage="not_sure",
        irrigation_history="not_sure",
        last_irrigation_date=None,
        soil_moisture="not_sure",
        drainage="not_sure",
        soil_texture="not_sure",
    )
    result = assess_water(ASSESSMENT_ID, unknown, None)
    assert result.data["water_attention"] in {
        "insufficient_information",
        "inspect_field",
    }
    _assert_never_irrigates(result)


def test_rain_forecast_only_yields_recheck_after_rain_without_drainage_risk():
    rain = _weather(daily=_rainy_days())

    # Good drainage, non-wet soil: re-check after rain is observed.
    result = assess_water(ASSESSMENT_ID, _intake(), rain)
    assert result.status == "complete"
    assert result.data["water_attention"] == "recheck_after_rain"
    assert result.data["water_context"]["precipitation_forecast_present"] is True
    assert result.data["water_context"]["rain_recheck_eligible"] is True
    _assert_never_irrigates(result)

    # Waterlogging risk present: inspection wins, recheck is not offered.
    waterlogged = assess_water(
        ASSESSMENT_ID, _intake(drainage="waterlogging"), rain
    )
    assert waterlogged.data["water_attention"] == "inspect_field"
    assert waterlogged.data["water_context"]["rain_recheck_eligible"] is False
    assert "drainage_or_saturation_inspection" in waterlogged.safety_flags
    _assert_never_irrigates(waterlogged)

    # Saturated soil: same conservative inspection outcome.
    saturated = assess_water(ASSESSMENT_ID, _intake(soil_moisture="wet"), rain)
    assert saturated.data["water_attention"] == "inspect_field"
    assert saturated.data["water_context"]["rain_recheck_eligible"] is False
    _assert_never_irrigates(saturated)


def test_cri_stage_is_inspection_language_not_irrigation():
    result = assess_water(ASSESSMENT_ID, _intake(growth_stage="cri"), _weather())

    assert result.data["water_attention"] == "inspect_field"
    assert "CRI" in result.summary
    assert all("irrigate now" not in check.lower() for check in result.checks)
    _assert_never_irrigates(result)

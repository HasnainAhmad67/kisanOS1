"""Weather enrichment + Water input-completeness tests.

Covers the Bahawalpur pilot upgrade:

- Weather (PART A): a full Open-Meteo payload yields unit-carrying values, a
  next-24-hour precipitation block built from the provider's own hourly rows,
  provider/fetch time, resolved grid, and the fixed plain-language forecast
  context. Provider failure stays fail-closed - nothing is fabricated.
- Water (PART B): structured ``input_completeness`` / ``missing_inputs``, the
  ``water_context`` label rules, 2-3 prioritized field checks, and the hard
  guarantee that no output states an irrigation quantity, duration, pump
  runtime or schedule.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.agents.water import assess_water
from app.agents.weather import (
    GRID_CONTEXT_NOTE,
    NO_24H_SERIES,
    NO_RAIN_FORECAST,
    RAIN_FORECAST,
    assess_weather,
)
from app.schemas import AgentResult, Source
from app.team_agents.water.schema import find_unsafe
from app.team_agents.weather.agent import WeatherAgent

ASSESSMENT_ID = "00000000-0000-4000-8000-000000000011"
PAKISTAN_TZ = ZoneInfo("Asia/Karachi")

# Irrigation guidance vocabulary that must never appear in a Water card.
# ``hours`` (plural) and ``schedule for`` are irrigation-run phrasing; the
# forecast window wording "next 24 hours" on the Weather card is not.
FORBIDDEN_WATER_WORDING = re.compile(
    r"\birrigate\b|\bliters?\b|\blitres?\b|\bgallons?\b|\bpumps?\b|\bhours\b"
    r"|\bdurations?\b|\bcubic\s+met(?:er|re)s?\b|\bschedule for\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------- weather


def _provider_payload(*, rainy: bool, hourly: bool = True) -> dict:
    """A realistic Open-Meteo response for the Bahawalpur Sadar grid."""
    now_local = datetime.now(UTC).astimezone(PAKISTAN_TZ)
    provider_time = now_local.replace(minute=0, second=0, microsecond=0)

    payload: dict = {
        "timezone": "Asia/Karachi",
        "current": {
            "time": provider_time.strftime("%Y-%m-%dT%H:%M"),
            "temperature_2m": 33.4,
            "apparent_temperature": 34.1,
            "relative_humidity_2m": 41,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 12.6,
            "wind_direction_10m": 180,
        },
        "daily": {
            "time": [
                provider_time.date().isoformat(),
                (provider_time.date() + timedelta(days=1)).isoformat(),
            ],
            "temperature_2m_max": [34.0, 35.0],
            "temperature_2m_min": [21.0, 22.0],
            "precipitation_sum": [36.0 if rainy else 0.0, 0.0],
            "precipitation_probability_max": [70 if rainy else 0, 0],
        },
    }

    if hourly:
        payload["hourly"] = {
            "time": [
                (provider_time + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:%M")
                for offset in range(0, 48)
            ],
            "precipitation": [0.0] + [1.5 if rainy else 0.0] * 47,
            "precipitation_probability": [0] + [70 if rainy else 0] * 47,
        }

    return payload


def _run_weather(monkeypatch: pytest.MonkeyPatch, payload: dict) -> AgentResult:
    monkeypatch.setattr(
        WeatherAgent,
        "fetch_live_weather",
        lambda self, lat, lon: payload,
    )
    return asyncio.run(
        assess_weather(ASSESSMENT_ID, {"area_code": "bahawalpur_sadar"})
    )


def test_weather_full_payload_reports_units_next24h_and_provenance(monkeypatch):
    result = _run_weather(monkeypatch, _provider_payload(rainy=True))

    assert result.status == "complete"
    data = result.data
    assert data["provider"] == "Open-Meteo"
    assert data["freshness"] == "fresh"
    assert data["location_name"] == "Bahawalpur Sadar"
    assert data["location_granularity"] == "tehsil_forecast_grid"
    # provider time, fetched time and timezone are all exposed.
    assert data["provider_observation_at"] and data["retrieved_at"]
    assert data["timezone"] == "Asia/Karachi"

    current = data["current"]
    assert current["temperature_c"] == pytest.approx(33.4)
    assert current["relative_humidity_pct"] == pytest.approx(41.0)
    assert current["precipitation_mm"] == pytest.approx(0.0)
    assert current["wind_speed_kmh"] == pytest.approx(12.6)

    window = data["next_24h"]
    # 24 hourly provider rows inside the window, each 1.5 mm - never estimated.
    assert window["hourly_samples"] == 24
    assert window["precipitation_total_mm"] == pytest.approx(36.0)
    assert window["precipitation_probability_max_pct"] == pytest.approx(70.0)
    assert window["window_start"] and window["window_end"]

    context = data["forecast_context"]
    assert context["precipitation_expected_next_24h"] is True
    assert context["statements"] == [RAIN_FORECAST, GRID_CONTEXT_NOTE]

    text = " ".join(result.observations)
    assert "°C" in text and "mm" in text and "km/h" in text and "%" in text
    assert GRID_CONTEXT_NOTE in result.observations
    assert RAIN_FORECAST in result.observations
    # Seven-day outlook is still passed through untouched.
    assert data["daily_outlook"][0]["precipitation_sum_mm"] == pytest.approx(36.0)
    assert result.sources and result.sources[0].publisher == "Open-Meteo"


def test_weather_without_rain_forecast_states_no_meaningful_precipitation(monkeypatch):
    result = _run_weather(monkeypatch, _provider_payload(rainy=False))

    context = result.data["forecast_context"]
    assert context["precipitation_expected_next_24h"] is False
    assert context["statements"][0] == NO_RAIN_FORECAST
    assert context["statements"][-1] == GRID_CONTEXT_NOTE
    assert result.data["next_24h"]["precipitation_total_mm"] == pytest.approx(0.0)
    assert NO_RAIN_FORECAST in result.observations


def test_weather_without_hourly_series_makes_no_rain_claim(monkeypatch):
    result = _run_weather(monkeypatch, _provider_payload(rainy=True, hourly=False))

    window = result.data["next_24h"]
    assert window["precipitation_total_mm"] is None
    assert window["hourly_samples"] == 0
    # Absent data stays absent; no number is synthesized to fill the gap.
    assert result.data["forecast_context"]["statements"][0] == NO_24H_SERIES
    assert result.data["forecast_context"]["precipitation_expected_next_24h"] is None


def test_weather_provider_failure_is_fail_closed(monkeypatch):
    def boom(self, lat, lon):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(WeatherAgent, "fetch_live_weather", boom)
    result = asyncio.run(
        assess_weather(ASSESSMENT_ID, {"area_code": "bahawalpur_sadar"})
    )

    assert result.status == "unavailable"
    assert "current" not in result.data
    assert "next_24h" not in result.data
    assert result.data["freshness"] == "unavailable"
    assert "no_simulated_weather_fallback" in result.safety_flags
    assert result.sources == []
    assert "no fallback weather is fabricated" in result.evidence_reason


def test_weather_output_never_gives_irrigation_guidance(monkeypatch):
    result = _run_weather(monkeypatch, _provider_payload(rainy=True))
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False).lower()

    assert "irrigate" not in dumped
    assert not re.search(r"\bliters?\b|\blitres?\b|\bpumps?\b", dumped)
    assert "irrigation schedule" not in dumped
    assert "no_crop_thresholds_applied" in result.safety_flags


# ----------------------------------------------------------------- water


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


def _daily(rows):
    return [
        {
            "date": date,
            "temperature_max_c": 33.0,
            "temperature_min_c": 20.0,
            "precipitation_sum_mm": total,
            "precipitation_probability_max_pct": probability,
        }
        for date, total, probability in rows
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
            "provider": "Open-Meteo",
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
            },
            "daily_outlook": _daily(
                [("2026-10-04", 0.0, 0), ("2026-10-05", 0.0, 0)]
            )
            if daily is None
            else daily,
        },
    )


def test_water_unknown_inputs_return_partial_with_exact_missing_inputs():
    result = assess_water(
        ASSESSMENT_ID,
        _intake(
            growth_stage="not_sure",
            irrigation_history="not_sure",
            last_irrigation_date=None,
            soil_moisture="not_sure",
            drainage="not_sure",
            soil_texture="not_sure",
        ),
        _weather(),
    )

    assert result.status == "partial"
    assert result.data["water_attention"] == "insufficient_information"
    assert result.data["input_completeness"] == {
        "growth_stage": "unknown",
        "irrigation_history": "unknown",
        "soil_texture": "unknown",
        "soil_moisture": "unknown",
        "drainage": "unknown",
        "weather_context": "fresh",
    }
    assert result.data["missing_inputs"] == [
        "growth_stage",
        "last_irrigation_date",
        "soil_moisture",
        "drainage",
    ]
    # The summary names exactly what is missing.
    for label in (
        "growth stage",
        "last irrigation date",
        "soil moisture",
        "drainage condition",
    ):
        assert label in result.summary
    assert result.summary.startswith("Water attention: insufficient_information.")
    assert result.data["water_context"]["label"] == "field_check_needed"
    assert 2 <= len(result.checks) <= 3
    assert result.data["irrigation_command"] is None


def test_water_complete_moist_good_drainage_with_fresh_weather_is_complete():
    result = assess_water(ASSESSMENT_ID, _intake(), _weather())

    assert result.status == "complete"
    assert result.data["missing_inputs"] == []
    assert result.data["input_completeness"] == {
        "growth_stage": "known",
        "irrigation_history": "known",
        "soil_texture": "known",
        "soil_moisture": "known",
        "drainage": "known",
        "weather_context": "fresh",
    }
    assert result.data["water_context"]["label"] == "forecast_context_only"
    assert result.summary.startswith("Water attention: monitor.")
    assert (
        "Farmer reports moist loamy soil, good drainage, "
        "and last irrigation on 2026-09-25." in result.summary
    )
    assert "Weather forecast is context only." in result.summary
    # Two verification checks - not a command.
    assert len(result.checks) == 2
    assert all("irrigate" not in check.lower() for check in result.checks)
    assert result.data["irrigation_command"] is None


def test_water_dry_soil_requests_a_field_check_not_irrigation():
    result = assess_water(ASSESSMENT_ID, _intake(soil_moisture="dry"), _weather())

    assert result.data["water_context"]["label"] == "field_check_needed"
    assert result.data["water_attention"] == "inspect_field"
    assert any("root depth" in check for check in result.checks)
    assert "dry" in result.summary.lower()
    dumped = json.dumps(result.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "irrigate now" not in dumped
    assert result.data["irrigation_command"] is None


@pytest.mark.parametrize("drainage", ["poor", "waterlogging"])
def test_water_poor_drainage_watches_drainage_without_irrigation_advice(drainage):
    result = assess_water(
        ASSESSMENT_ID, _intake(drainage=drainage), _weather()
    )

    assert result.data["water_context"]["label"] == "watch_drainage"
    assert result.data["water_attention"] == "inspect_field"
    assert "drainage" in result.checks[0].lower()
    assert "drainage_or_saturation_inspection" in result.safety_flags
    assert result.data["irrigation_command"] is None
    assert "irrigate" not in json.dumps(
        result.model_dump(mode="json"), ensure_ascii=False
    ).lower()


def test_water_weather_context_state_follows_provider_freshness():
    fresh = assess_water(ASSESSMENT_ID, _intake(), _weather())
    assert fresh.data["input_completeness"]["weather_context"] == "fresh"
    assert fresh.data["missing_inputs"] == []

    stale = assess_water(
        ASSESSMENT_ID,
        _intake(),
        _weather(status="stale", freshness="stale_or_timestamp_missing"),
    )
    assert stale.status == "partial"
    assert stale.data["input_completeness"]["weather_context"] == "stale"
    assert stale.data["missing_inputs"] == ["fresh_weather_forecast"]
    assert "fresh weather forecast" in stale.summary

    offline = assess_water(ASSESSMENT_ID, _intake(), None)
    assert offline.status == "partial"
    assert offline.data["input_completeness"]["weather_context"] == "unavailable"
    assert offline.data["missing_inputs"] == ["fresh_weather_forecast"]


def test_no_water_output_contains_irrigation_quantities_or_schedules():
    scenarios = [
        _intake(),
        _intake(soil_moisture="dry"),
        _intake(soil_moisture="wet"),
        _intake(drainage="poor"),
        _intake(drainage="waterlogging"),
        _intake(growth_stage="cri"),
        _intake(
            growth_stage="not_sure",
            irrigation_history="not_sure",
            last_irrigation_date=None,
            soil_moisture="not_sure",
            drainage="not_sure",
        ),
    ]
    weathers = [
        _weather(),
        _weather(status="stale", freshness="stale_or_timestamp_missing"),
        _weather(status="unavailable", freshness="unavailable", with_sources=False),
        None,
    ]

    for intake in scenarios:
        for weather in weathers:
            result = assess_water(ASSESSMENT_ID, intake, weather)
            payload = result.model_dump(mode="json")
            dumped = json.dumps(payload, ensure_ascii=False)

            assert FORBIDDEN_WATER_WORDING.search(dumped) is None, dumped
            assert find_unsafe(dumped) is None, dumped
            assert payload["data"]["irrigation_command"] is None
            assert 2 <= len(payload["checks"]) <= 3
            assert payload["status"] in {"complete", "partial", "unavailable"}

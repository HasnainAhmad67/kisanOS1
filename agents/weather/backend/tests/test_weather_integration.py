from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.agents.advisor import build_farm_plan
from app.agents.weather import assess_weather
from app.team_agents.weather.agent import WeatherAgent

LOCAL = ZoneInfo("Asia/Karachi")


def pmd_payload(*, age_hours: int = 0, cache_status: str = "live") -> dict:
    now = datetime.now(LOCAL).replace(minute=0, second=0, microsecond=0) - timedelta(hours=age_hours)
    cycle = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    fetched = datetime.now(UTC) - timedelta(hours=age_hours)
    return {
        "city": {
            "slug": "bahawalpur",
            "name": "Bahawalpur",
            "province": "Punjab",
            "lat": 29.4,
            "lng": 71.7,
            "wmo_codes": [41700, 41701],
        },
        "station": "BAHAWALPUR,CITY",
        "observed_at": now.isoformat(timespec="minutes"),
        "is_live": cache_status != "stale",
        "temperature": 34.2,
        "humidity_pct": 41,
        "rainfall_mm": 0.0,
        "rainfall_24h_mm": 0.2,
        "wind_kmh": 8.7,
        "wind_direction": "NW",
        "dew_point": 19.0,
        "pressure_hpa": 1004.0,
        "visibility": 8.0,
        "condition": {"label": "Mainly clear"},
        "forecast": {
            "name": "ICON",
            "org": "DWD Germany",
            "cycle": cycle.strftime("%Y%m%d%H"),
            "hours": [
                {
                    "at": (now + timedelta(hours=index + 1)).isoformat(timespec="minutes"),
                    "temp": 34.0 - index * 0.2,
                    "rain_mm": 0.0,
                    "condition": "Mainly clear",
                }
                for index in range(12)
            ],
        },
        "_kisanos_weather": {
            "provider": "pmd_ffd",
            "cache_status": cache_status,
            "source_fetch_at": fetched.isoformat(),
            "served_at": datetime.now(UTC).isoformat(),
            "cache_age_seconds": age_hours * 3600,
            "snapshot_sha256": "p" * 64,
        },
    }


def open_meteo_payload(*, cache_status: str = "live", age_hours: int = 0) -> dict:
    local_now = datetime.now(LOCAL).replace(minute=0, second=0, microsecond=0)
    fetched = datetime.now(UTC) - timedelta(hours=age_hours)
    return {
        "timezone": "Asia/Karachi",
        "hourly_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation_probability": "%",
            "precipitation": "mm",
            "wind_speed_10m": "km/h",
            "wind_direction_10m": "°",
        },
        "daily_units": {
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_sum": "mm",
            "precipitation_probability_max": "%",
            "wind_speed_10m_max": "km/h",
        },
        "hourly": {
            "time": [(local_now + timedelta(hours=index)).isoformat(timespec="minutes") for index in range(72)],
            "temperature_2m": [28.0] * 72,
            "relative_humidity_2m": [55] * 72,
            "precipitation_probability": [5] * 72,
            "precipitation": [0.0] * 72,
            "wind_speed_10m": [9.0] * 72,
            "wind_direction_10m": [190] * 72,
            "weather_code": [1] * 72,
        },
        "daily": {
            "time": [(local_now.date() + timedelta(days=index)).isoformat() for index in range(7)],
            "temperature_2m_max": [33.0] * 7,
            "temperature_2m_min": [20.0] * 7,
            "precipitation_sum": [0.0] * 7,
            "precipitation_probability_max": [5] * 7,
            "wind_speed_10m_max": [12.0] * 7,
            "weather_code": [1] * 7,
        },
        "_kisanos_weather": {
            "provider": "open-meteo",
            "cache_status": cache_status,
            "source_fetch_at": fetched.isoformat(),
            "served_at": datetime.now(UTC).isoformat(),
            "cache_age_seconds": age_hours * 3600,
            "snapshot_sha256": "o" * 64,
        },
    }


def patch_providers(monkeypatch, *, pmd=None, open_meteo=None, pmd_error=None, open_meteo_error=None):
    def pmd_call(_self, _lat, _lon):
        if pmd_error:
            raise RuntimeError(pmd_error)
        return pmd if pmd is not None else pmd_payload()

    def open_meteo_call(_self, _lat, _lon):
        if open_meteo_error:
            raise RuntimeError(open_meteo_error)
        return open_meteo if open_meteo is not None else open_meteo_payload()

    monkeypatch.setattr(WeatherAgent, "fetch_pmd_weather", pmd_call)
    monkeypatch.setattr(WeatherAgent, "fetch_open_meteo_outlook", open_meteo_call)


def test_weather_result_preserves_both_provider_roles_and_product_metadata(monkeypatch):
    patch_providers(monkeypatch)
    result = asyncio.run(assess_weather("assessment-1", {"area_code": "bahawalpur_sadar"}))

    assert result.status == "complete"
    payload = result.model_dump(mode="json")
    assert {
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
    }.issubset(payload)
    assert payload["agent_id"] == "weather"
    assert "PMD station temperature: 34.2 °C." in payload["observations"]
    assert any("rainfall" in item.lower() and "mm" in item for item in payload["observations"])
    assert any("72-hour outlook" in item for item in payload["observations"])
    assert any("seven-day outlook" in item for item in payload["observations"])
    assert payload["checks"]
    assert len(payload["data"]["weather_watch_signals"]) == 2
    assert all("not a field observation" in item["interpretation"] for item in payload["data"]["weather_watch_signals"])
    assert any("does not establish the cause" in item for item in payload["possible_causes"])
    assert result.data["weather_status"] == "weather_fresh"
    providers = result.data["providers"]
    pmd = providers["pmd"]
    meteo = providers["open_meteo"]
    assert pmd["current"]["status"] == "fresh"
    assert pmd["current"]["values"]["temperature_c"] == 34.2
    assert pmd["current"]["observed_at"]
    assert pmd["current"]["retrieved_at"]
    assert pmd["location_resolution"]["resolved_city"] == "Bahawalpur"
    assert pmd["location_resolution"]["granularity"] == "nearest_city_station"
    assert len(pmd["forecast_12h"]["hourly"]) == 12
    assert pmd["forecast_12h"]["forecast_issue_at"]
    assert len(meteo["hourly_72h"]["values"]) == 72
    assert len(meteo["daily_7d"]["values"]) == 7
    assert meteo["forecast_issue_at"] is None
    assert "not forecast confidence" in meteo["hourly_72h"]["precipitation_probability_note"]
    assert result.data["current"]["temperature_c"] == 34.2  # Compatibility alias is PMD-only.
    assert len(result.data["hourly_next_12h"]) == 12
    assert len(result.data["hourly_next_72h"]) == 72
    assert len(result.sources) == 2
    assert {source.publisher for source in result.sources} == {
        "Pakistan Meteorological Department — Flood Forecasting Division",
        "Open-Meteo",
    }
    assert "no_provider_confidence_claims" in result.safety_flags
    assert "not field measurements" in result.evidence_reason.lower()


def test_pmd_failure_keeps_open_meteo_forecast_available(monkeypatch):
    patch_providers(monkeypatch, pmd_error="offline")
    result = asyncio.run(assess_weather("assessment-2", {"area_code": "bahawalpur_sadar"}))
    assert result.status == "partial"
    assert result.data["providers"]["pmd"]["current"]["weather_status"] == "weather_unavailable"
    assert result.data["providers"]["open_meteo"]["hourly_72h"]["weather_status"] == "weather_fresh"
    assert len(result.data["hourly_next_72h"]) == 72
    assert result.data["current"] is None


def test_open_meteo_failure_keeps_pmd_current_and_short_horizon(monkeypatch):
    patch_providers(monkeypatch, open_meteo_error="offline")
    result = asyncio.run(assess_weather("assessment-3", {"area_code": "hasilpur"}))
    assert result.status == "partial"
    assert result.data["providers"]["pmd"]["current"]["weather_status"] == "weather_fresh"
    assert len(result.data["hourly_next_12h"]) == 12
    assert result.data["providers"]["open_meteo"]["hourly_72h"]["weather_status"] == "weather_unavailable"
    assert result.data["hourly_next_72h"] == []


def test_pmd_observations_older_than_six_hours_are_withheld(monkeypatch):
    patch_providers(monkeypatch, pmd=pmd_payload(age_hours=7))
    result = asyncio.run(assess_weather("assessment-4", {"area_code": "bahawalpur_sadar"}))
    assert result.status == "partial"  # Open-Meteo remains independently useful.
    pmd = result.data["providers"]["pmd"]
    assert pmd["current"]["weather_status"] == "weather_unavailable"
    assert pmd["current"]["values"] is None
    assert "older than the six-hour" in pmd["current"]["reason"]
    assert pmd["forecast_12h"]["weather_status"] == "weather_stale"
    assert "provider_stale_data" in result.safety_flags


def test_stale_provider_badge_is_audited_even_if_overall_weather_is_partial(monkeypatch):
    patch_providers(monkeypatch, pmd=pmd_payload(age_hours=2, cache_status="stale"))
    result = asyncio.run(assess_weather("assessment-5", {"area_code": "bahawalpur_sadar"}))
    assert result.status == "partial"
    assert result.data["providers"]["pmd"]["current"]["weather_status"] == "weather_stale"
    assert "provider_stale_data" in result.safety_flags
    plan = build_farm_plan(
        "assessment-5", {"growth_stage": "not_sure", "irrigation_history": "not_sure", "symptoms": []}, [result]
    )
    assert any(conflict["topic"] == "weather_freshness" for conflict in plan.conflicts)


def test_open_meteo_stale_cache_is_distinct_and_explicit(monkeypatch):
    patch_providers(monkeypatch, open_meteo=open_meteo_payload(cache_status="stale", age_hours=2))
    result = asyncio.run(assess_weather("assessment-6", {"area_code": "bahawalpur_sadar"}))
    assert result.status == "partial"
    panel = result.data["providers"]["open_meteo"]
    assert panel["hourly_72h"]["weather_status"] == "weather_stale"
    assert panel["daily_7d"]["retrieved_at"]
    assert panel["cache"]["status"] == "stale"
    assert "provider_stale_data" in result.safety_flags


def test_both_provider_failures_return_unavailable_without_synthetic_values(monkeypatch):
    patch_providers(monkeypatch, pmd_error="offline", open_meteo_error="offline")
    result = asyncio.run(assess_weather("assessment-7", {"area_code": "bahawalpur_sadar"}))
    assert result.status == "unavailable"
    assert result.data["weather_status"] == "weather_unavailable"
    assert result.data["current"] is None
    assert result.data["hourly_next_12h"] == []
    assert result.data["hourly_next_72h"] == []
    assert "weather_not_fresh" in result.safety_flags


def test_exact_coordinates_are_not_echoed_in_data_or_source_notes(monkeypatch):
    patch_providers(monkeypatch)
    result = asyncio.run(
        assess_weather(
            "assessment-8",
            {"area_code": "bahawalpur_sadar", "latitude": 29.456789, "longitude": 71.765432, "gps_consent": True},
        )
    )
    serialized = str(result.model_dump(mode="json"))
    assert "29.456789" not in serialized
    assert "71.765432" not in serialized

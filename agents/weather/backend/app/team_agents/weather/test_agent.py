from __future__ import annotations

import json
import sqlite3
import stat
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

try:
    from agents.weather.agent import BAHAWALPUR_TEHSILS, WeatherAgent
except ImportError:
    from app.team_agents.weather.agent import BAHAWALPUR_TEHSILS, WeatherAgent

LOCAL = ZoneInfo("Asia/Karachi")


def provider_payload(*, age_hours: int = 0) -> dict:
    now = datetime.now(LOCAL).replace(minute=0, second=0, microsecond=0) - timedelta(hours=age_hours)
    hours = [now + timedelta(hours=index) for index in range(72)]
    daily_days = [now.date() + timedelta(days=index) for index in range(7)]
    return {
        "latitude": 29.4,
        "longitude": 71.7,
        "timezone": "Asia/Karachi",
        "timezone_abbreviation": "PKT",
        "utc_offset_seconds": 18000,
        "current_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
            "wind_speed_10m": "km/h",
            "wind_direction_10m": "°",
        },
        "current": {
            "time": now.isoformat(timespec="minutes"),
            "temperature_2m": 28.5,
            "relative_humidity_2m": 45,
            "precipitation": 0.0,
            "wind_speed_10m": 9.0,
            "wind_direction_10m": 190,
            "weather_code": 1,
        },
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
            "time": [value.isoformat(timespec="minutes") for value in hours],
            "temperature_2m": [28.0] * 72,
            "relative_humidity_2m": [45] * 72,
            "precipitation_probability": [10] * 72,
            "precipitation": [0.0] * 72,
            "wind_speed_10m": [12.0] * 72,
            "wind_direction_10m": [190] * 72,
            "weather_code": [2] * 72,
        },
        "daily": {
            "time": [value.isoformat() for value in daily_days],
            "temperature_2m_max": [33.0] * 7,
            "temperature_2m_min": [20.0] * 7,
            "precipitation_sum": [0.0] * 7,
            "precipitation_probability_max": [10] * 7,
            "wind_speed_10m_max": [17.0] * 7,
            "weather_code": [2] * 7,
        },
    }


def pmd_payload(*, age_hours: int = 0, cache_status: str = "live") -> dict:
    now = datetime.now(LOCAL).replace(minute=0, second=0, microsecond=0) - timedelta(hours=age_hours)
    utc_cycle = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    forecast_hours = [now + timedelta(hours=index + 1) for index in range(12)]
    fetched_at = datetime.now(UTC) - timedelta(hours=age_hours)
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
            "cycle": utc_cycle.strftime("%Y%m%d%H"),
            "hours": [
                {
                    "at": value.isoformat(timespec="minutes"),
                    "temp": 34.0 - index * 0.2,
                    "rain_mm": 0.0,
                    "condition": "Mainly clear",
                }
                for index, value in enumerate(forecast_hours)
            ],
        },
        "_kisanos_weather": {
            "provider": "pmd_ffd",
            "cache_status": cache_status,
            "source_fetch_at": fetched_at.isoformat(),
            "served_at": datetime.now(UTC).isoformat(),
            "cache_age_seconds": int(age_hours * 3600),
            "snapshot_sha256": "p" * 64,
        },
    }


def open_meteo_payload(*, cache_status: str = "live", age_hours: int = 0) -> dict:
    payload = provider_payload()
    fetched_at = datetime.now(UTC) - timedelta(hours=age_hours)
    payload["_kisanos_weather"] = {
        "provider": "open-meteo",
        "cache_status": cache_status,
        "source_fetch_at": fetched_at.isoformat(),
        "served_at": datetime.now(UTC).isoformat(),
        "cache_age_seconds": int(age_hours * 3600),
        "snapshot_sha256": "o" * 64,
    }
    return payload


def test_resolves_only_supported_areas_and_preserves_compatibility_methods():
    agent = WeatherAgent(cache_path=":memory:", retries=0)
    assert set(BAHAWALPUR_TEHSILS) == {
        "bahawalpur_sadar",
        "ahmadpur_east",
        "yazman",
        "hasilpur",
        "khairpur_tamewali",
    }
    name, lat, lon, elevation = agent.resolve_coordinates("bahawalpur sadar")
    assert (name, lat, lon, elevation) == ("Bahawalpur Sadar", 29.3956, 71.6836, 116.0)
    with pytest.raises(ValueError, match="Unsupported"):
        agent.resolve_coordinates("unknown-town")
    assert agent.resolve_coordinates(None, 29.4, 71.7)[0] == "Consented coordinates"
    with pytest.raises(ValueError, match="both latitude"):
        agent.resolve_coordinates(None, 29.4, None)
    with pytest.raises(ValueError, match="pilot area"):
        agent.resolve_coordinates(None, 33.7, 73.1)
    assert callable(agent.fetch_live_weather)
    assert callable(agent.fetch_pmd_weather)
    assert callable(agent.fetch_open_meteo_outlook)


def test_custom_coordinates_require_consent_before_any_provider_call(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "weather.sqlite3"), retries=0)
    called = False

    def forbidden(*_args):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    monkeypatch.setattr(agent, "fetch_pmd_weather", forbidden)
    monkeypatch.setattr(agent, "fetch_open_meteo_outlook", forbidden)
    with pytest.raises(ValueError, match="GPS consent"):
        agent.analyze(lat=29.4, lon=71.7)
    assert called is False


def test_standalone_report_separates_pmd_observation_from_open_meteo_outlook(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "weather.sqlite3"), retries=0)
    monkeypatch.setattr(agent, "fetch_pmd_weather", lambda *_args: pmd_payload())
    monkeypatch.setattr(agent, "fetch_open_meteo_outlook", lambda *_args: open_meteo_payload())
    report = agent.analyze(assessment_id="assessment-1", enable_ai=False)
    assert report.assessment_id == "assessment-1"
    assert report.status == "complete"
    assert report.evidence_band == "low"
    assert report.weather_details is not None
    assert report.weather_details.current is not None
    assert report.weather_details.current.temperature_c == 34.2  # PMD owns current conditions.
    assert len(report.weather_details.providers["pmd"]["forecast_12h"]["hourly"]) == 12
    assert len(report.weather_details.hourly_next_72h) == 72  # Open-Meteo owns the outlook.
    assert len(report.weather_details.daily_outlook_7d) == 7
    assert report.weather_details.providers["open_meteo"]["forecast_issue_at"] is None
    payload = report.model_dump(mode="json")
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
    assert payload["summary"].count(".") >= 2
    assert any("rainfall" in item.lower() and "mm" in item for item in payload["observations"])
    assert any("72-hour" in item and "precipitation probability" in item for item in payload["observations"])
    assert any("seven-day" in item and "precipitation probability" in item for item in payload["observations"])
    assert payload["checks"]
    assert len(report.weather_details.weather_watch_signals) == 2
    assert all(
        "not a field observation" in item["interpretation"] for item in report.weather_details.weather_watch_signals
    )
    assert (
        "not forecast confidence"
        in report.weather_details.providers["open_meteo"]["hourly_72h"]["precipitation_probability_note"]
    )
    assert any("does not establish the cause" in item for item in report.possible_causes)
    assert "not a field measurement" in report.evidence_reason.lower()
    assert {source.publisher for source in report.sources} == {
        "Pakistan Meteorological Department — Flood Forecasting Division",
        "Open-Meteo",
    }
    assert all(
        "confidence" not in str(item).lower() or "no_provider_confidence_claims" in str(item).lower()
        for item in report.model_dump()
    )


def test_stale_pmd_current_does_not_hide_fresh_open_meteo_forecast(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "weather.sqlite3"), retries=0)
    monkeypatch.setattr(
        agent,
        "fetch_pmd_weather",
        lambda *_args: pmd_payload(age_hours=7, cache_status="stale"),
    )
    monkeypatch.setattr(agent, "fetch_open_meteo_outlook", lambda *_args: open_meteo_payload())
    report = agent.analyze(enable_ai=False)
    assert report.status == "partial"
    assert report.weather_details is not None
    pmd = report.weather_details.providers["pmd"]
    assert pmd["current"]["status"] == "unavailable"
    assert pmd["current"]["values"] is None
    assert pmd["forecast_12h"]["status"] == "stale"
    assert report.weather_details.providers["open_meteo"]["hourly_72h"]["status"] == "fresh"


def test_missing_retrieval_metadata_is_not_labeled_fresh(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "missing-retrieval.sqlite3"), retries=0)
    pmd = pmd_payload()
    pmd["_kisanos_weather"].pop("source_fetch_at")
    open_meteo = open_meteo_payload()
    open_meteo["_kisanos_weather"].pop("source_fetch_at")
    monkeypatch.setattr(agent, "fetch_pmd_weather", lambda *_args: pmd)
    monkeypatch.setattr(agent, "fetch_open_meteo_outlook", lambda *_args: open_meteo)
    report = agent.analyze(enable_ai=False)
    assert report.status == "stale"
    assert report.weather_details is not None
    assert report.weather_details.retrieved_at is None
    assert report.weather_details.providers["pmd"]["current"]["status"] == "unavailable"
    assert report.weather_details.providers["open_meteo"]["hourly_72h"]["status"] == "stale"


def test_provider_validators_reject_out_of_range_and_nonmonotonic_forecasts(tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "validation.sqlite3"), retries=0)
    valid_open_meteo = provider_payload()
    assert agent.provider_client.valid_open_meteo_outlook(valid_open_meteo)
    bad_number = deepcopy(valid_open_meteo)
    bad_number["hourly"]["temperature_2m"][10] = 500
    assert not agent.provider_client.valid_open_meteo_outlook(bad_number)
    bad_time = deepcopy(valid_open_meteo)
    bad_time["hourly"]["time"][10] = bad_time["hourly"]["time"][9]
    assert not agent.provider_client.valid_open_meteo_outlook(bad_time)
    invalid_pmd = pmd_payload()
    invalid_pmd["forecast"]["hours"].pop()
    assert not agent.provider_client.valid_pmd_payload(invalid_pmd)


def test_open_meteo_forecast_request_uses_only_forecast_products(monkeypatch, tmp_path):
    agent = WeatherAgent(
        open_meteo_url="https://api.open-meteo.com/v1/forecast",
        cache_path=str(tmp_path / "weather.sqlite3"),
        retries=0,
    )
    captured: dict[str, str] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _size):
            return json.dumps(provider_payload()).encode()

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = str(timeout)
        captured["user_agent"] = request.get_header("User-agent")
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    result = agent.fetch_open_meteo_outlook(29.3956, 71.6836)
    assert result["_kisanos_weather"]["cache_status"] == "live"
    assert "forecast_hours=72" in captured["url"]
    assert "forecast_days=7" in captured["url"]
    assert "temperature_unit=celsius" in captured["url"]
    assert "timezone=Asia%2FKarachi" in captured["url"]
    assert "current=" not in captured["url"]
    assert float(captured["timeout"]) <= 3.5
    assert captured["user_agent"].startswith("KisanOS-WeatherAgent/")


def test_pmd_request_uses_documented_endpoint_and_validates_twelve_hour_schema(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "weather.sqlite3"), retries=0)
    captured: dict[str, str] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _size):
            return json.dumps(pmd_payload()).encode()

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["user_agent"] = request.get_header("User-agent")
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    result = agent.fetch_pmd_weather(29.3956, 71.6836)
    assert result["_kisanos_weather"]["provider"] == "pmd_ffd"
    assert "ffd.pmd.gov.pk/weather/current" in captured["url"]
    assert "lat=29.395600" in captured["url"] and "lng=71.683600" in captured["url"]
    assert captured["user_agent"].startswith("KisanOS-WeatherAgent/")


def test_open_meteo_snapshot_hash_survives_coordinate_sanitized_cache_hit(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "snapshot.sqlite3"), retries=0)
    monkeypatch.setattr(
        agent.provider_client,
        "_request_open_meteo_outlook",
        lambda *_args: provider_payload(),
    )
    live = agent.fetch_open_meteo_outlook(29.3956, 71.6836)
    cached = agent.fetch_open_meteo_outlook(29.3956, 71.6836)
    assert live["_kisanos_weather"]["snapshot_sha256"] == cached["_kisanos_weather"]["snapshot_sha256"]
    assert "latitude" in live and "longitude" in live
    assert "latitude" not in cached and "longitude" not in cached
    assert cached["_kisanos_weather"]["cache_status"] == "fresh_cache"


def test_network_failure_uses_only_real_bounded_stale_cache(monkeypatch, tmp_path):
    cache_path = tmp_path / "weather.sqlite3"
    first = WeatherAgent(cache_path=str(cache_path), retries=0)
    monkeypatch.setattr(first, "_request", lambda _lat, _lon: provider_payload())
    assert first.fetch_live_weather(29.3956, 71.6836)["_kisanos_weather"]["cache_status"] == "live"
    key = first._location_key(29.3956, 71.6836, f"{first.api_url}|legacy-current-bundle")
    old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    with sqlite3.connect(cache_path) as connection:
        connection.execute(
            "UPDATE weather_cache SET fetched_at = ? WHERE cache_key = ?",
            (old_time, key),
        )

    second = WeatherAgent(cache_path=str(cache_path), retries=0)
    monkeypatch.setattr(
        second,
        "_request",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    result = second.fetch_live_weather(29.3956, 71.6836)
    assert result["_kisanos_weather"]["cache_status"] == "stale"
    assert result["_kisanos_weather"]["cache_age_seconds"] >= 7000


def test_provider_failures_are_independent_and_return_unavailable_without_fabrication(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "empty.sqlite3"), retries=0)
    monkeypatch.setattr(
        agent,
        "fetch_pmd_weather",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(
        agent,
        "fetch_open_meteo_outlook",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    report = agent.analyze(enable_ai=False)
    assert report.status == "unavailable"
    assert report.weather_details is not None
    assert report.weather_details.current is None
    assert report.weather_details.providers["pmd"]["weather_status"] == "weather_unavailable"
    assert report.weather_details.providers["open_meteo"]["weather_status"] == "weather_unavailable"
    assert "no_synthetic_fallback" in report.safety_flags
    with pytest.raises(RuntimeError, match="Synthetic weather fallback is disabled"):
        agent.get_resilient_fallback_weather("Bahawalpur Sadar", 29.4, 71.7)


def test_urdu_and_roman_urdu_are_deterministic_and_schema_valid(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "urdu.sqlite3"), retries=0)
    monkeypatch.setattr(agent, "fetch_pmd_weather", lambda *_args: pmd_payload())
    monkeypatch.setattr(agent, "fetch_open_meteo_outlook", lambda *_args: open_meteo_payload())
    report = agent.analyze(enable_ai=True, locale="ur")
    assert report.AI_ENHANCED is not None
    assert report.AI_ENHANCED.mode == "deterministic_translation"
    assert report.AI_ENHANCED.priority_level == "low"
    assert "34.2" in report.AI_ENHANCED.roman_urdu
    assert report.AI_ENHANCED.urdu_summary
    assert "AI_ENHANCED" in report.model_dump(mode="json")
    roman_report = agent.analyze(enable_ai=False, locale="roman_ur")
    assert "weather grid" in roman_report.summary.lower()


def test_weather_cache_key_is_coarse_hashed_and_file_is_private(monkeypatch, tmp_path):
    path = tmp_path / "private" / "weather.sqlite3"
    agent = WeatherAgent(cache_path=str(path), retries=0)
    key = agent._location_key(29.3956, 71.6836, f"{agent.api_url}|legacy-current-bundle")
    assert "29.3956" not in key and "71.6836" not in key
    monkeypatch.setattr(agent, "_request", lambda *_args: provider_payload())
    agent.fetch_live_weather(29.3956, 71.6836)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with sqlite3.connect(path) as connection:
        stored = connection.execute("SELECT cache_key, payload_json FROM weather_cache").fetchone()
    assert stored[0] == key
    assert "29.3956" not in stored[1]
    assert '"latitude"' not in stored[1]
    assert '"longitude"' not in stored[1]


def test_legacy_backend_fetch_interface_remains_callable(monkeypatch, tmp_path):
    agent = WeatherAgent(cache_path=str(tmp_path / "adapter.sqlite3"), retries=0)
    monkeypatch.setattr(agent, "_request", lambda _lat, _lon: provider_payload())
    resolved = agent.resolve_coordinates("hasilpur")
    raw = agent.fetch_live_weather(resolved[1], resolved[2])
    assert isinstance(raw["hourly"], dict)
    assert isinstance(raw["daily"], dict)
    assert raw["_kisanos_weather"]["provider"] == "open-meteo"

from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import AREAS, get_settings
from app.schemas import AgentResult, Source
from app.team_agents.weather.agent import WeatherAgent

VERSION = "weather-provider-adapter-1.0.0"


def _parse_provider_time(value: str | None, zone: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = (
            datetime.fromisoformat(value[:-1]).replace(tzinfo=UTC)
            if value.endswith("Z")
            else datetime.fromisoformat(value)
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(zone))
        return parsed.astimezone(UTC)
    except (ValueError, KeyError):
        return None


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


async def assess_weather(assessment_id: str, intake: dict[str, Any]) -> AgentResult:
    now = datetime.now(UTC)
    area_code = intake["area_code"]
    area = AREAS[area_code]
    # Exact coordinates are used only after explicit consent; output exposes granularity, not the coordinates.
    lat = intake.get("latitude") if intake.get("gps_consent") else None
    lon = intake.get("longitude") if intake.get("gps_consent") else None
    location_key = area_code
    if lat is not None and lon is not None:
        location_key = "consented-coarse-coordinate"
    settings = get_settings()
    try:
        agent = WeatherAgent(open_meteo_url=settings.open_meteo_url)
        resolved_name, resolved_lat, resolved_lon, _elev = agent.resolve_coordinates(
            location_key if lat is None else None, lat, lon
        )
        raw = await asyncio.wait_for(
            asyncio.to_thread(agent.fetch_live_weather, resolved_lat, resolved_lon),
            timeout=settings.weather_timeout_seconds + 1,
        )
        current = raw.get("current") or {}
        daily = raw.get("daily") or {}
        timezone_name = str(raw.get("timezone") or "Asia/Karachi")
        provider_time = _parse_provider_time(current.get("time"), timezone_name)
        freshness_age = (now - provider_time).total_seconds() / 3600 if provider_time else None
        if freshness_age is None or freshness_age > 6:
            status = "stale"
        else:
            status = "complete"
        details = {
            "location_name": str(resolved_name),
            "location_granularity": "consented_coordinates" if lat is not None else "tehsil_forecast_grid",
            "timezone": timezone_name,
            "provider_observation_at": provider_time.isoformat() if provider_time else None,
            "retrieved_at": now.isoformat(),
            "freshness": "fresh" if status == "complete" else "stale_or_timestamp_missing",
            "current": {
                "temperature_c": _finite(current.get("temperature_2m")),
                "relative_humidity_pct": _finite(current.get("relative_humidity_2m")),
                "precipitation_mm": _finite(current.get("precipitation")),
                "wind_speed_kmh": _finite(current.get("wind_speed_10m")),
                "weather_code": current.get("weather_code"),
            },
            "daily_outlook": [],
        }
        for index, day in enumerate((daily.get("time") or [])[:7]):
            row = {"date": day}
            for field, source in (
                ("temperature_max_c", "temperature_2m_max"),
                ("temperature_min_c", "temperature_2m_min"),
                ("precipitation_sum_mm", "precipitation_sum"),
                ("precipitation_probability_max_pct", "precipitation_probability_max"),
            ):
                values = daily.get(source) or []
                row[field] = _finite(values[index]) if index < len(values) else None
            details["daily_outlook"].append(row)
        source = Source(
            title="Open-Meteo forecast API",
            url="https://open-meteo.com/en/docs",
            publisher="Open-Meteo",
            geography="Forecast grid near selected Bahawalpur area; not a field-level measurement",
            retrieved_at=now,
            source_status="official",
            note="Provider values shown without crop-risk thresholds. Forecast is not an agronomic prediction.",
        )
        observations = []
        temp = details["current"]["temperature_c"]
        if temp is not None:
            observations.append(f"Open-Meteo reports {temp:g} °C at the selected forecast grid.")
        rain = details["current"]["precipitation_mm"]
        if rain is not None:
            observations.append(f"Provider reports {rain:g} mm current-interval precipitation.")
        if not observations:
            observations.append("Provider response contained no current values that passed validation.")
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="weather",
            status=status,
            summary="Weather values are provider-reported forecast-grid context, not field measurements.",
            observations=observations,
            checks=[],
            evidence_band="low" if status == "complete" else "not_calibrated",
            evidence_reason="Open-Meteo response with explicit location resolution and provider time; no local forecast accuracy is claimed.",
            sources=[source],
            provider_or_model="open-meteo",
            version=VERSION,
            created_at=now,
            safety_flags=["not_field_sensor", "no_crop_thresholds_applied"],
            data=details,
            input_evidence=[f"Selected area: {area['name']}", "No exact coordinates retained in response"],
        )
    except Exception as exc:  # noqa: BLE001 - provider failures must abstain without failing other agents.
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="weather",
            status="unavailable",
            summary="Weather data is unavailable; other assessment agents continue without weather-driven rules.",
            observations=[],
            checks=[],
            evidence_band="not_calibrated",
            evidence_reason=f"Provider request or validation failed ({type(exc).__name__}); no fallback weather is fabricated.",
            sources=[],
            provider_or_model="open-meteo-unavailable",
            version=VERSION,
            created_at=now,
            safety_flags=["no_simulated_weather_fallback", "weather_not_used_for_water"],
            data={
                "location_name": str(area["name"]),
                "location_granularity": "tehsil_forecast_grid",
                "freshness": "unavailable",
            },
            input_evidence=[f"Selected area: {area['name']}"],
        )

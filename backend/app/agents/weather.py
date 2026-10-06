from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import AREAS, get_settings
from app.schemas import AgentResult, Source
from app.team_agents.weather.agent import WeatherAgent

VERSION = "weather-provider-adapter-1.0.0"

# Deterministic plain-language forecast context. Fixed wording only: no crop
# thresholds, no crop-specific claim, and never a statement about this field.
NO_RAIN_FORECAST = (
    "No meaningful precipitation is currently forecast in the next 24 hours; "
    "confirm field moisture before any water decision."
)
RAIN_FORECAST = (
    "Precipitation is forecast, but it does not confirm effective root-zone recharge."
)
GRID_CONTEXT_NOTE = (
    "Forecast values are grid context, not measurements from this field."
)
NO_24H_SERIES = (
    "The provider returned no next-24-hour precipitation series, "
    "so no rainfall statement is made."
)


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


def _local_wall_clock(value: Any) -> datetime | None:
    """Provider-local wall clock (no offset) so hourly rows line up exactly."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw[:-1] if raw.endswith("Z") else raw)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _next_24h(hourly: Any, provider_local_time: Any) -> dict[str, Any]:
    """Aggregate the provider's own hourly series over the next 24 hours.

    Nothing is interpolated: rows outside the window are ignored, and a
    missing series stays ``null`` with an explicit basis instead of a guess.
    """
    window: dict[str, Any] = {
        "window_start": None,
        "window_end": None,
        "precipitation_total_mm": None,
        "precipitation_probability_max_pct": None,
        "hourly_samples": 0,
        "basis": "no usable hourly series in the provider response",
    }

    start = _local_wall_clock(provider_local_time)
    if not isinstance(hourly, dict) or start is None:
        return window

    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        return window

    end = start + timedelta(hours=24)
    precip_series = hourly.get("precipitation")
    probability_series = hourly.get("precipitation_probability")

    total: float | None = None
    peak: float | None = None
    samples = 0

    for index, stamp in enumerate(times):
        moment = _local_wall_clock(stamp)
        if moment is None or not (start < moment <= end):
            continue
        samples += 1

        if isinstance(precip_series, list) and index < len(precip_series):
            value = _finite(precip_series[index])
            if value is not None and 0 <= value <= 1000:
                total = (total or 0.0) + value

        if isinstance(probability_series, list) and index < len(probability_series):
            value = _finite(probability_series[index])
            if value is not None and 0 <= value <= 100:
                peak = value if peak is None else max(peak, value)

    if not samples:
        return window

    window.update(
        {
            "window_start": start.isoformat(timespec="minutes"),
            "window_end": end.isoformat(timespec="minutes"),
            "precipitation_total_mm": round(total, 2) if total is not None else None,
            "precipitation_probability_max_pct": (
                round(peak, 1) if peak is not None else None
            ),
            "hourly_samples": samples,
            "basis": "provider hourly forecast series, rows inside the window only",
        }
    )
    return window


def _context_statements(window: dict[str, Any]) -> tuple[list[str], bool | None]:
    """The two fixed forecast sentences plus the always-on grid caveat."""
    total = window.get("precipitation_total_mm")
    probability = window.get("precipitation_probability_max_pct")

    if total is not None:
        expected: bool | None = total > 0
    elif probability is not None:
        expected = probability > 0
    else:
        expected = None

    if expected is None:
        return [NO_24H_SERIES, GRID_CONTEXT_NOTE], None
    return [RAIN_FORECAST if expected else NO_RAIN_FORECAST, GRID_CONTEXT_NOTE], expected


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
        hourly = raw.get("hourly") or {}
        daily = raw.get("daily") or {}
        timezone_name = str(raw.get("timezone") or "Asia/Karachi")
        provider_time = _parse_provider_time(current.get("time"), timezone_name)
        freshness_age = (now - provider_time).total_seconds() / 3600 if provider_time else None
        if freshness_age is None or freshness_age > 6:
            status = "stale"
        else:
            status = "complete"
        next_24h = _next_24h(hourly, current.get("time"))
        statements, rain_expected = _context_statements(next_24h)
        details = {
            "provider": "Open-Meteo",
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
            "next_24h": next_24h,
            "forecast_context": {
                "precipitation_expected_next_24h": rain_expected,
                "statements": statements,
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

        # Five items maximum so the Results card never hides the context lines.
        observations: list[str] = []
        readings: list[str] = []
        temperature = details["current"]["temperature_c"]
        humidity = details["current"]["relative_humidity_pct"]
        wind = details["current"]["wind_speed_kmh"]
        if temperature is not None:
            readings.append(f"{temperature:g} °C")
        if humidity is not None:
            readings.append(f"{humidity:g}% relative humidity")
        if wind is not None:
            readings.append(f"{wind:g} km/h wind speed")
        if readings:
            observations.append(
                f"Open-Meteo reports {_join(readings)} at the selected forecast grid."
            )
        rain = details["current"]["precipitation_mm"]
        if rain is not None:
            observations.append(
                f"Open-Meteo reports {rain:g} mm current-interval precipitation "
                "at the selected forecast grid."
            )
        total_24h = next_24h.get("precipitation_total_mm")
        probability_24h = next_24h.get("precipitation_probability_max_pct")
        if total_24h is not None or probability_24h is not None:
            pieces: list[str] = []
            if total_24h is not None:
                pieces.append(f"{total_24h:g} mm precipitation")
            if probability_24h is not None:
                pieces.append(f"up to {probability_24h:g}% precipitation probability")
            observations.append(
                f"Next 24 hours at the selected forecast grid: {_join(pieces)}."
            )
        if not observations:
            observations.append("Provider response contained no current values that passed validation.")
        observations.extend(statements)

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
                "provider": "Open-Meteo",
                "location_name": str(area["name"]),
                "location_granularity": "tehsil_forecast_grid",
                "freshness": "unavailable",
            },
            input_evidence=[f"Selected area: {area['name']}"],
        )

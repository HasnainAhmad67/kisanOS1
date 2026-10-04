from __future__ import annotations

import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import AREAS, get_settings
from app.schemas import AgentResult, Source
from app.team_agents.weather.agent import WeatherAgent

logger = logging.getLogger("kisanos.weather")
VERSION = "weather-provider-adapter-3.0.0"
PMD_WIDGET_URL = "https://ffd.pmd.gov.pk/weather-widget"
OPEN_METEO_DOCS_URL = "https://open-meteo.com/en/docs"
PAKISTAN_TZ = "Asia/Karachi"
CURRENT_MAX_AGE_SECONDS = 6 * 60 * 60


def _finite(value: Any, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    if minimum is not None and result < minimum:
        return None
    if maximum is not None and result > maximum:
        return None
    return result


def _timestamp(value: Any, assumed_timezone: str = PAKISTAN_TZ) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(assumed_timezone))
        return parsed.astimezone(UTC)
    except (ValueError, ZoneInfoNotFoundError):
        return None


def _iso(value: Any) -> str | None:
    parsed = _timestamp(value)
    return parsed.isoformat() if parsed else None


def _cache_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    value = raw.get("_kisanos_weather") if isinstance(raw, dict) else None
    return value if isinstance(value, dict) else {}


def _weather_status(status: str) -> str:
    return {
        "fresh": "weather_fresh",
        "stale": "weather_stale",
        "unavailable": "weather_unavailable",
    }.get(status, "weather_unavailable")


def _pmd_panel(
    raw: dict[str, Any] | None, failure: str | None, now: datetime, area_name: str
) -> tuple[dict[str, Any], list[str]]:
    meta = _cache_metadata(raw)
    cache_status = meta.get("cache_status", "unavailable")
    retrieved_at = _timestamp(meta.get("source_fetch_at"))
    observed_at_raw = raw.get("observed_at") if raw else None
    observed_at = _timestamp(observed_at_raw)
    observation_age = (now - observed_at).total_seconds() if observed_at else None
    retrieved_age = (now - retrieved_at).total_seconds() if retrieved_at else None
    city = raw.get("city") if raw and isinstance(raw.get("city"), dict) else {}
    forecast = raw.get("forecast") if raw and isinstance(raw.get("forecast"), dict) else {}
    location = {
        "selected_area": area_name,
        "resolved_city": city.get("name") if isinstance(city.get("name"), str) else None,
        "province": city.get("province") if isinstance(city.get("province"), str) else None,
        "station": raw.get("station") if raw and isinstance(raw.get("station"), str) else None,
        "wmo_codes": city.get("wmo_codes") if isinstance(city.get("wmo_codes"), list) else None,
        "granularity": "nearest_city_station",
        "field_level_precision_claimed": False,
    }
    current_status = "unavailable"
    current_values: dict[str, Any] | None = None
    current_reason = failure
    if raw and observed_at and retrieved_at and observation_age is not None:
        if 0 <= observation_age <= CURRENT_MAX_AGE_SECONDS:
            condition = raw.get("condition") if isinstance(raw.get("condition"), dict) else {}
            current_values = {
                "temperature_c": _finite(raw.get("temperature"), -80, 65),
                "relative_humidity_pct": _finite(raw.get("humidity_pct"), 0, 100),
                "rainfall_mm": _finite(raw.get("rainfall_mm"), 0, 5000),
                "rainfall_24h_mm": _finite(raw.get("rainfall_24h_mm"), 0, 5000),
                "wind_speed_kmh": _finite(raw.get("wind_kmh"), 0, 500),
                "wind_direction": raw.get("wind_direction") if isinstance(raw.get("wind_direction"), str) else None,
                "dew_point_c": _finite(raw.get("dew_point"), -100, 65),
                "pressure_hpa": _finite(raw.get("pressure_hpa"), 0, 1200),
                "visibility_km": _finite(raw.get("visibility"), 0, 500),
                "condition": condition.get("label") if isinstance(condition.get("label"), str) else None,
                "station": location["station"],
            }
            current_status = (
                "stale" if cache_status == "stale" or raw.get("is_live") is False or retrieved_age is None else "fresh"
            )
            if current_status == "stale":
                current_reason = "The last successful PMD observation is shown with an explicit stale badge."
        elif observation_age < 0:
            current_reason = "PMD observation time is in the future; values are withheld."
        else:
            current_reason = "PMD observation is older than the six-hour current-conditions limit; values are withheld."

    cycle = forecast.get("cycle")
    run_at = None
    if isinstance(cycle, str) and len(cycle) == 10 and cycle.isdigit():
        try:
            run_at = datetime.strptime(cycle, "%Y%m%d%H").replace(tzinfo=UTC)
        except ValueError:
            run_at = None
    if run_at is None:
        run_at = _timestamp(forecast.get("issued_at"))
    run_age = (now - run_at).total_seconds() if run_at else None
    forecast_rows: list[dict[str, Any]] = []
    raw_hours = forecast.get("hours") if isinstance(forecast.get("hours"), list) else []
    previous: datetime | None = None
    for item in raw_hours[:12]:
        if not isinstance(item, dict):
            continue
        timestamp = _timestamp(item.get("at"))
        if timestamp is None or (previous is not None and timestamp <= previous):
            continue
        previous = timestamp
        forecast_rows.append(
            {
                "time": timestamp.isoformat(),
                "temperature_c": _finite(item.get("temp"), -80, 65),
                "precipitation_mm": _finite(item.get("rain_mm"), 0, 1000),
                "condition": item.get("condition") if isinstance(item.get("condition"), str) else None,
            }
        )
    forecast_status = "unavailable"
    forecast_reason = failure
    if len(forecast_rows) == 12 and retrieved_at:
        if (
            cache_status == "stale"
            or retrieved_age is None
            or (run_age is not None and (run_age < -3600 or run_age > CURRENT_MAX_AGE_SECONDS))
        ):
            forecast_status = "stale"
            forecast_reason = "PMD 12-hour forecast is shown with an explicit stale badge."
        else:
            forecast_status = "fresh"
            forecast_reason = None
    elif raw:
        forecast_reason = "PMD did not return twelve validated hourly-interpolated periods."

    source_age = int(meta.get("cache_age_seconds")) if isinstance(meta.get("cache_age_seconds"), (int, float)) else None
    provider_statuses = [current_status, forecast_status]
    provider_status = (
        "fresh" if "fresh" in provider_statuses else "stale" if "stale" in provider_statuses else "unavailable"
    )
    if "stale" in provider_statuses and "fresh" in provider_statuses:
        provider_status = "partial"
    pmd_data = {
        "provider": "Pakistan Meteorological Department — Flood Forecasting Division",
        "provider_id": "pmd_ffd",
        "source_url": PMD_WIDGET_URL,
        "weather_status": "weather_partial" if provider_status == "partial" else _weather_status(provider_status),
        "cache": {"status": cache_status, "age_seconds": source_age},
        "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
        "source_snapshot_sha256": meta.get("snapshot_sha256"),
        "location_resolution": location,
        "current": {
            "status": current_status,
            "weather_status": _weather_status(current_status),
            "observed_at": observed_at.isoformat() if observed_at else None,
            "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
            "timezone": PAKISTAN_TZ,
            "freshness_age_seconds": int(observation_age)
            if observation_age is not None and observation_age >= 0
            else None,
            "units": {
                "temperature": "°C",
                "relative_humidity": "%",
                "rainfall": "mm",
                "rainfall_24h": "mm",
                "wind_speed": "km/h",
                "dew_point": "°C",
                "pressure": "hPa",
                "visibility": "km",
            },
            "values": current_values if current_status != "unavailable" else None,
            "reason": current_reason,
        },
        "forecast_12h": {
            "status": forecast_status,
            "weather_status": _weather_status(forecast_status),
            "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
            "forecast_issue_at": run_at.isoformat() if run_at else None,
            "forecast_model": forecast.get("name"),
            "forecast_model_organization": forecast.get("organization") or forecast.get("org"),
            "timezone": PAKISTAN_TZ,
            "location_resolution": location,
            "units": {"temperature": "°C", "precipitation": "mm"},
            "interpolation": "PMD hourly-interpolated forecast",
            "hourly": forecast_rows if forecast_status != "unavailable" else [],
            "reason": forecast_reason,
        },
    }
    observations: list[str] = []
    if current_values and current_status != "unavailable":
        city_name = location["resolved_city"] or area_name
        station = location["station"] or "resolved PMD station"
        observations.append(
            f"PMD FFD reports station conditions for {city_name} ({station}); this is nearby city/station context, not a field measurement."
        )
        for field, label, unit in (
            ("temperature_c", "PMD station temperature", "°C"),
            ("relative_humidity_pct", "PMD relative humidity", "%"),
            ("rainfall_mm", "PMD-reported rainfall", "mm"),
            ("wind_speed_kmh", "PMD wind speed", "km/h"),
        ):
            value = current_values.get(field)
            if value is not None:
                observations.append(f"{label}: {value:g} {unit}.")
    if forecast_status != "unavailable":
        observations.append("PMD's 12-hour hourly-interpolated forecast is provided in its own provider panel.")
    return pmd_data, observations


def _open_meteo_panel(
    raw: dict[str, Any] | None,
    failure: str | None,
    now: datetime,
    area_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    meta = _cache_metadata(raw)
    cache_status = meta.get("cache_status", "unavailable")
    retrieved_at = _timestamp(meta.get("source_fetch_at"))
    served_at = _timestamp(meta.get("served_at"))
    age_seconds = meta.get("cache_age_seconds") if isinstance(meta.get("cache_age_seconds"), (int, float)) else None
    timezone_name = raw.get("timezone") if raw and isinstance(raw.get("timezone"), str) else PAKISTAN_TZ
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        timezone_name = PAKISTAN_TZ
        raw = None
        failure = "InvalidTimezone"
    hourly_raw = raw.get("hourly") if raw and isinstance(raw.get("hourly"), dict) else {}
    daily_raw = raw.get("daily") if raw and isinstance(raw.get("daily"), dict) else {}
    hourly_units = raw.get("hourly_units") if raw and isinstance(raw.get("hourly_units"), dict) else {}
    daily_units = raw.get("daily_units") if raw and isinstance(raw.get("daily_units"), dict) else {}
    hourly: list[dict[str, Any]] = []
    times = hourly_raw.get("time") if isinstance(hourly_raw.get("time"), list) else []
    for index, hour in enumerate(times[:72]):
        if not isinstance(hour, str):
            continue
        row: dict[str, Any] = {"time": hour}
        for field, source, low, high in (
            ("temperature_c", "temperature_2m", -80, 65),
            ("relative_humidity_pct", "relative_humidity_2m", 0, 100),
            ("precipitation_probability_pct", "precipitation_probability", 0, 100),
            ("precipitation_mm", "precipitation", 0, 2000),
            ("wind_speed_kmh", "wind_speed_10m", 0, 500),
            ("wind_direction_deg", "wind_direction_10m", 0, 360),
            ("weather_code", "weather_code", 0, 1000),
        ):
            values = hourly_raw.get(source) if isinstance(hourly_raw.get(source), list) else []
            row[field] = _finite(values[index], low, high) if index < len(values) else None
        hourly.append(row)
    daily: list[dict[str, Any]] = []
    days = daily_raw.get("time") if isinstance(daily_raw.get("time"), list) else []
    for index, day in enumerate(days[:7]):
        if not isinstance(day, str):
            continue
        row: dict[str, Any] = {"date": day}
        for field, source, low, high in (
            ("temperature_max_c", "temperature_2m_max", -80, 65),
            ("temperature_min_c", "temperature_2m_min", -80, 65),
            ("precipitation_sum_mm", "precipitation_sum", 0, 5000),
            ("precipitation_probability_max_pct", "precipitation_probability_max", 0, 100),
            ("wind_speed_max_kmh", "wind_speed_10m_max", 0, 500),
            ("weather_code", "weather_code", 0, 1000),
        ):
            values = daily_raw.get(source) if isinstance(daily_raw.get(source), list) else []
            row[field] = _finite(values[index], low, high) if index < len(values) else None
        daily.append(row)
    if not hourly and not daily:
        status = "unavailable"
    elif cache_status == "stale" or retrieved_at is None or (served_at and (now - served_at).total_seconds() < -3600):
        status = "stale"
    else:
        status = "fresh"
    provider_data = {
        "provider": "Open-Meteo",
        "provider_id": "open_meteo",
        "source_url": OPEN_METEO_DOCS_URL,
        "weather_status": _weather_status(status),
        "cache": {"status": cache_status, "age_seconds": int(age_seconds) if age_seconds is not None else None},
        "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
        "source_snapshot_sha256": meta.get("snapshot_sha256"),
        "location_resolution": {
            "selected_area": area_name,
            "granularity": "forecast_grid_near_selected_area",
            "field_level_precision_claimed": False,
        },
        "forecast_issue_at": None,
        "forecast_issue_note": "The selected Open-Meteo response fields do not expose a verified model-run timestamp; retrieval time is not represented as issue time.",
        "timezone": timezone_name,
        "hourly_72h": {
            "status": status,
            "weather_status": _weather_status(status),
            "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
            "timezone": timezone_name,
            "units": {
                "temperature": hourly_units.get("temperature_2m", "°C"),
                "relative_humidity": hourly_units.get("relative_humidity_2m", "%"),
                "precipitation_probability": hourly_units.get("precipitation_probability", "%"),
                "precipitation": hourly_units.get("precipitation", "mm"),
                "wind_speed": hourly_units.get("wind_speed_10m", "km/h"),
                "wind_direction": hourly_units.get("wind_direction_10m", "°"),
            },
            "precipitation_probability_note": "Probability of precipitation only; it is not forecast confidence.",
            "values": hourly,
            "reason": failure if status == "unavailable" else None,
        },
        "daily_7d": {
            "status": status,
            "weather_status": _weather_status(status),
            "retrieved_at": retrieved_at.isoformat() if retrieved_at else None,
            "timezone": timezone_name,
            "units": {
                "temperature": daily_units.get("temperature_2m_max", "°C"),
                "precipitation": daily_units.get("precipitation_sum", "mm"),
                "precipitation_probability": daily_units.get("precipitation_probability_max", "%"),
                "wind_speed": daily_units.get("wind_speed_10m_max", "km/h"),
            },
            "precipitation_probability_note": "Probability of precipitation only; it is not forecast confidence.",
            "values": daily,
            "reason": failure if status == "unavailable" else None,
        },
    }
    observations = []
    if status != "unavailable":
        observations.append(
            "Open-Meteo supplies a separate forecast-grid 72-hour detail and seven-day outlook; neither is a field observation."
        )
    return provider_data, hourly, daily, observations


async def assess_weather(assessment_id: str, intake: dict[str, Any]) -> AgentResult:
    """Run two independent providers and return the existing typed AgentResult envelope."""
    now = datetime.now(UTC)
    area_code = intake.get("area_code")
    area = AREAS.get(area_code)
    if area is None:
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="weather",
            status="unavailable",
            summary="Weather data is unavailable because the selected pilot area could not be resolved.",
            evidence_reason="Unsupported area; no weather request was made.",
            provider_or_model="pmd-ffd+open-meteo",
            version=VERSION,
            created_at=now,
            safety_flags=["weather_unavailable", "no_synthetic_fallback"],
            data={"weather_status": "weather_unavailable", "freshness": "unavailable"},
        )

    settings = get_settings()
    lat = intake.get("latitude") if intake.get("gps_consent") else None
    lon = intake.get("longitude") if intake.get("gps_consent") else None
    try:
        agent = WeatherAgent(
            open_meteo_url=settings.open_meteo_url,
            cache_path=str(settings.weather_cache_path),
            timeout_seconds=min(3.5, settings.weather_timeout_seconds),
            retries=1,
            pmd_current_url=settings.pmd_weather_current_url,
            pmd_refresh_seconds=settings.pmd_min_refresh_seconds,
            open_meteo_refresh_seconds=settings.open_meteo_min_refresh_seconds,
            current_max_age_seconds=settings.weather_current_max_cache_age_seconds,
            forecast_max_stale_seconds=settings.weather_forecast_max_cache_age_seconds,
        )
        selected_name, resolved_lat, resolved_lon, _ = agent.resolve_coordinates(
            area_code if lat is None else None, lat, lon
        )
    except (ValueError, OSError) as exc:
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="weather",
            status="unavailable",
            summary="Weather data is unavailable for the selected location; other assessment agents continue.",
            evidence_reason=f"Location/provider configuration rejected ({type(exc).__name__}); no fallback location was used.",
            provider_or_model="pmd-ffd+open-meteo",
            version=VERSION,
            created_at=now,
            safety_flags=["weather_unavailable", "no_synthetic_fallback"],
            data={"weather_status": "weather_unavailable", "freshness": "unavailable"},
            input_evidence=[f"Selected area: {area['name']}"],
        )

    # Both specialist sources execute concurrently; an unavailable source does not cancel its peer.
    tasks = {
        "pmd": asyncio.create_task(asyncio.to_thread(agent.fetch_pmd_weather, resolved_lat, resolved_lon)),
        "open_meteo": asyncio.create_task(
            asyncio.to_thread(agent.fetch_open_meteo_outlook, resolved_lat, resolved_lon)
        ),
    }
    done, pending = await asyncio.wait(tasks.values(), timeout=settings.weather_timeout_seconds + 1)
    for task in pending:
        task.cancel()
    raw_results: dict[str, dict[str, Any] | None] = {"pmd": None, "open_meteo": None}
    errors: dict[str, str | None] = {"pmd": None, "open_meteo": None}
    for provider_id, task in tasks.items():
        if task not in done:
            errors[provider_id] = "ProviderTimeout"
            continue
        try:
            result = task.result()
            if isinstance(result, dict):
                raw_results[provider_id] = result
            else:
                errors[provider_id] = "InvalidProviderResponse"
        except Exception as exc:  # noqa: BLE001 - one source's failure must never block the other provider.
            errors[provider_id] = type(exc).__name__
            logger.info(
                "weather provider unavailable",
                extra={"assessment_id": assessment_id, "provider_id": provider_id, "error_type": type(exc).__name__},
            )

    pmd_data, pmd_observations = _pmd_panel(raw_results["pmd"], errors["pmd"], now, str(area["name"]))
    om_data, hourly, daily, om_observations = _open_meteo_panel(
        raw_results["open_meteo"], errors["open_meteo"], now, str(area["name"])
    )
    products = [
        pmd_data["current"]["status"],
        pmd_data["forecast_12h"]["status"],
        om_data["hourly_72h"]["status"],
        om_data["daily_7d"]["status"],
    ]
    fresh_count = products.count("fresh")
    usable_count = sum(value in {"fresh", "stale"} for value in products)
    if fresh_count == len(products):
        status = "complete"
        weather_status = "weather_fresh"
    elif fresh_count:
        status = "partial"
        weather_status = "weather_partial"
    elif usable_count:
        status = "stale"
        weather_status = "weather_stale"
    else:
        status = "unavailable"
        weather_status = "weather_unavailable"
    freshness = (
        "fresh"
        if status == "complete"
        else "partial"
        if status == "partial"
        else "stale"
        if status == "stale"
        else "unavailable"
    )

    current = pmd_data["current"]["values"]
    observations = pmd_observations + om_observations
    possible_causes: list[str] = []
    weather_watch_signals: list[dict[str, Any]] = []
    checks = [
        "Compare the town/station or forecast-grid information with actual farm conditions and check the latest official PMD advisory; these data are not field measurements."
    ]

    # Surface key rainfall facts in the standard AgentResult fields as well as in
    # the full provider panels. Keep amounts and probabilities source-attributed.
    pmd_current_values = pmd_data["current"].get("values") or {}
    for field, label in (
        ("rainfall_mm", "PMD-reported rainfall (source reporting interval not inferred)"),
        ("rainfall_24h_mm", "PMD-reported rainfall over 24 hours"),
    ):
        value = _finite(pmd_current_values.get(field), 0, 5000)
        if value is not None:
            observations.append(f"{label}: {value:g} mm.")

    hourly_rain = [
        float(row["precipitation_mm"]) for row in hourly if isinstance(row.get("precipitation_mm"), (int, float))
    ]
    hourly_probability = [
        float(row["precipitation_probability_pct"])
        for row in hourly
        if isinstance(row.get("precipitation_probability_pct"), (int, float))
    ]
    daily_rain = [
        float(row["precipitation_sum_mm"]) for row in daily if isinstance(row.get("precipitation_sum_mm"), (int, float))
    ]
    daily_probability = [
        float(row["precipitation_probability_max_pct"])
        for row in daily
        if isinstance(row.get("precipitation_probability_max_pct"), (int, float))
    ]

    if hourly:
        next_72h_text = "Open-Meteo next-72-hour outlook is available."
        if hourly_rain:
            next_72h_text += f" Maximum hourly precipitation shown: {max(hourly_rain):g} mm."
        if hourly_probability:
            next_72h_text += (
                f" Maximum hourly precipitation probability: {max(hourly_probability):g}% "
                "(event probability, not forecast confidence)."
            )
        observations.append(next_72h_text)

    if daily:
        seven_day_text = "Open-Meteo seven-day outlook is available."
        if daily_rain:
            seven_day_text += f" Maximum daily precipitation total shown: {max(daily_rain):g} mm."
        if daily_probability:
            seven_day_text += (
                f" Maximum daily precipitation probability: {max(daily_probability):g}% "
                "(event probability, not forecast confidence)."
            )
        observations.append(seven_day_text)

    if hourly and ((hourly_rain and max(hourly_rain) > 0) or (hourly_probability and max(hourly_probability) > 0)):
        weather_watch_signals.append(
            {
                "signal": "forecast_precipitation_next_72h",
                "provider": "Open-Meteo",
                "maximum_hourly_precipitation_mm": max(hourly_rain) if hourly_rain else None,
                "maximum_hourly_precipitation_probability_pct": max(hourly_probability) if hourly_probability else None,
                "interpretation": "Forecast watch only; not a field observation, crop-risk rating, or forecast-confidence score.",
            }
        )
    if daily and ((daily_rain and max(daily_rain) > 0) or (daily_probability and max(daily_probability) > 0)):
        weather_watch_signals.append(
            {
                "signal": "forecast_precipitation_next_7d",
                "provider": "Open-Meteo",
                "maximum_daily_precipitation_total_mm": max(daily_rain) if daily_rain else None,
                "maximum_daily_precipitation_probability_pct": max(daily_probability) if daily_probability else None,
                "interpretation": "Forecast watch only; not a field observation, crop-risk rating, or forecast-confidence score.",
            }
        )
    if weather_watch_signals:
        possible_causes.append(
            "Forecast precipitation is a possible meteorological context to compare with field observations; it does not establish the cause of any crop symptoms."
        )

    if not observations:
        observations.append("PMD and Open-Meteo did not return usable data; no substitute weather was generated.")
    if pmd_data["current"]["status"] == "stale" or pmd_data["forecast_12h"]["status"] == "stale":
        observations.append(
            "At least one PMD product is stale; its own provider panel carries the stale badge and timestamp."
        )
    if om_data["hourly_72h"]["status"] == "stale":
        observations.append(
            "The Open-Meteo outlook is stale; do not interpret its retrieval time as a model issue time."
        )

    pmd_retrieved = _timestamp(pmd_data.get("retrieved_at"))
    om_retrieved = _timestamp(om_data.get("retrieved_at"))
    sources = [
        Source(
            title="PMD FFD public weather widget product",
            url=PMD_WIDGET_URL,
            publisher="Pakistan Meteorological Department — Flood Forecasting Division",
            geography=f"Resolved PMD town/station near {area['name']}; not field-level",
            published_at=_timestamp(pmd_data["current"].get("observed_at")),
            retrieved_at=pmd_retrieved,
            source_status="official",
            note="PMD current observation and its hourly-interpolated 12-hour forecast remain separate from the Open-Meteo outlook.",
        ),
        Source(
            title="Open-Meteo Forecast API documentation",
            url=OPEN_METEO_DOCS_URL,
            publisher="Open-Meteo",
            geography=f"Forecast grid near {area['name']}; not a field sensor",
            retrieved_at=om_retrieved,
            source_status="official",
            note="Used only for 72-hour and seven-day forecasts. Precipitation probability is not forecast confidence.",
        ),
    ]

    data = {
        "schema_version": "kisanos.weather.v3",
        "weather_status": weather_status,
        "freshness": freshness,
        "weather_watch_signals": weather_watch_signals,
        "timezone": PAKISTAN_TZ,
        "selected_location": {
            "area_code": area_code,
            "area_name": str(area["name"]),
            "consented_coordinates_used": lat is not None and lon is not None,
            "resolved_input_label": selected_name,
            "field_level_precision_claimed": False,
            "privacy_note": "Exact farmer coordinates are not copied into provider panels, source notes, or logs.",
        },
        "providers": {"pmd": pmd_data, "open_meteo": om_data},
        # Compatibility aliases for existing React code; current is PMD-only, outlook arrays Open-Meteo-only.
        "current": current,
        "hourly_next_12h": pmd_data["forecast_12h"]["hourly"],
        "hourly_next_72h": hourly,
        "daily_outlook_7d": daily,
        "precipitation_probability_note": "Precipitation probability is a weather-event probability, not provider or forecast confidence.",
    }
    summary = (
        "PMD current and short-horizon products and Open-Meteo outlooks are retained as separate weather sources. One or more products are stale; check source timestamps and official updates before relying on them."
        if status == "stale"
        else "Verified weather data are unavailable from PMD FFD and/or Open-Meteo for this assessment. No substitute conditions or crop-level weather risk were generated; other agents can continue."
        if status == "unavailable"
        else f"PMD current/12-hour station products and Open-Meteo 72-hour/7-day outlooks are reported separately for {area['name']}. These are town/station or forecast-grid context, not field measurements; review per-product freshness and weather-watch signals."
    )
    evidence_reason = (
        "Every provider product preserves its own source, retrieval/observation/model-run time when available, timezone, location resolution, units, cache age and freshness. City/grid forecasts are not field measurements."
        if fresh_count
        else "No provider product is fresh. Stale data are individually badged; values beyond the six-hour current-observation limit are withheld. No synthetic fallback is generated."
    )
    flags = [
        "city_grid_not_field_sensor",
        "no_weather_driven_irrigation_rule",
        "no_provider_confidence_claims",
        "no_synthetic_fallback",
    ]
    if any(value == "stale" for value in products):
        flags.append("provider_stale_data")
    if any(value == "unavailable" for value in products):
        flags.append("provider_partial_or_unavailable")
    if not fresh_count:
        flags.append("weather_not_fresh")

    # Audit logs contain provider/status/hash only—never coordinates, forecast values, or farmer notes.
    for provider_id, panel in (("pmd_ffd", pmd_data), ("open_meteo", om_data)):
        logger.info(
            "weather provider product evaluated",
            extra={
                "assessment_id": assessment_id,
                "provider_id": provider_id,
                "weather_status": panel.get("weather_status"),
                "cache_status": (panel.get("cache") or {}).get("status"),
                "snapshot_sha256": panel.get("source_snapshot_sha256"),
            },
        )

    return AgentResult(
        assessment_id=assessment_id,
        agent_id="weather",
        status=status,
        summary=summary,
        observations=observations,
        possible_causes=possible_causes,
        checks=checks,
        evidence_band="low" if fresh_count else "not_calibrated",
        evidence_reason=evidence_reason,
        sources=sources,
        provider_or_model="pmd-ffd+open-meteo",
        version=VERSION,
        created_at=now,
        safety_flags=flags,
        data=data,
        input_evidence=[
            f"Farmer-confirmed pilot area: {area['name']}",
            "Exact farmer coordinates are not retained in the Weather result.",
        ],
    )

"""Weather Agent -> Water Agent contract normalization.

The connected Weather adapter (``app.agents.weather``, Weather v1.0.0)
returns provider-reported values shaped as::

    data.current                current-interval readings
    data.daily_outlook          seven forecast days (date, temps, precip, probability)
    data.freshness              "fresh" | "stale_or_timestamp_missing" | "unavailable"
    data.retrieved_at           when the backend retrieved the provider payload
    data.provider_observation_at  the provider's own observation timestamp
    sources                     Open-Meteo provenance records
    status                      "complete" | "stale" | "unavailable" | ...

The canonical Water Agent v2.0.0 (``app.team_agents.water.agent``) consumes
dated forecast *products*::

    data.providers.open_meteo.hourly_72h   {status, values, retrieved_at}
    data.providers.open_meteo.daily_7d     {status, values, retrieved_at}

``normalize_weather_for_water`` converts the first shape into the second.

Rules:
- Values are copied, never invented. Daily rows come straight from
  ``data.daily_outlook``.
- The connected adapter does not expose an hourly precipitation series, so
  ``hourly_72h`` stays explicitly unavailable with an empty value list; no
  hourly numbers are synthesized.
- Weather that is stale, partial, unavailable, or missing required fields is
  reported as an explicit stale/unavailable context so Water v2.0.0 reduces
  confidence and stays conservative instead of treating it as fresh.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas import AgentResult

PANEL_VERSION = "weather-water-panel-1.0.0"


def _as_dict(value: Any) -> dict[str, Any]:
    """Accept an AgentResult, a plain dict, or nothing."""
    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json")
        except TypeError:
            dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}

    return {}


def _iso(value: Any) -> str | None:
    """Return a timezone-aware ISO timestamp, or None when untrusted."""
    if isinstance(value, datetime):
        return value.isoformat() if value.tzinfo is not None else None

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def _product_status(status: str, freshness: str) -> str:
    """Map the Weather card status + freshness onto Water's product states."""
    if status == "stale" or freshness == "stale_or_timestamp_missing":
        return "stale"

    if status == "complete" and freshness == "fresh":
        return "fresh"

    return "unavailable"


def _source_records(raw_sources: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for item in raw_sources or []:
        source = _as_dict(item)

        if not source:
            continue

        title = str(source.get("title") or "").strip()
        url = str(source.get("url") or "").strip()
        publisher = str(source.get("publisher") or "").strip()
        source_status = str(source.get("source_status") or "").strip()
        retrieved_at = _iso(source.get("retrieved_at"))

        if not (title and url and publisher and retrieved_at):
            continue

        records.append(
            {
                "title": title,
                "url": url,
                "publisher": publisher,
                "retrieved_at": retrieved_at,
                "source_status": source_status or "unverified",
            }
        )

    return records


def normalize_weather_for_water(
    weather_result: AgentResult | dict[str, Any] | None,
) -> dict[str, Any]:
    """Convert the connected Weather AgentResult into the Water v2.0.0 panel.

    Returns a weather-envelope dict with ``status``, ``data.providers`` and
    ``sources`` in the exact structure ``evaluate_water`` consumes. Weather
    that cannot be trusted is passed through as an explicit stale or
    unavailable context - never as fresh data.
    """
    root = _as_dict(weather_result)
    data_raw = _as_dict(root.get("data"))

    status = str(root.get("status") or "").strip() or "unavailable"
    freshness = str(data_raw.get("freshness") or "").strip()
    product = _product_status(status, freshness)

    daily_rows = [
        dict(row)
        for row in (data_raw.get("daily_outlook") or [])
        if isinstance(row, dict)
    ]

    retrieved_at = _iso(data_raw.get("retrieved_at")) or _iso(
        data_raw.get("provider_observation_at")
    )

    hourly_panel: dict[str, Any] = {
        "status": "unavailable",
        "values": [],
        "retrieved_at": retrieved_at,
        "note": (
            "The connected Weather adapter does not expose an hourly "
            "precipitation series; no hourly values are synthesized."
        ),
    }

    daily_panel: dict[str, Any] = {
        "status": product if daily_rows else "unavailable",
        "values": daily_rows,
        "retrieved_at": retrieved_at,
    }

    return {
        "status": product,
        "data": {
            "weather_status": product,
            "freshness": product,
            "retrieved_at": retrieved_at,
            "location_name": data_raw.get("location_name"),
            "timezone": data_raw.get("timezone"),
            "current": data_raw.get("current") or {},
            "daily_outlook": daily_rows,
            "normalization": {
                "module": "app.services.weather_panel",
                "version": PANEL_VERSION,
                "weather_status_in": status,
                "weather_freshness_in": freshness or None,
            },
            "providers": {
                "open_meteo": {
                    "hourly_72h": hourly_panel,
                    "daily_7d": daily_panel,
                }
            },
        },
        "sources": _source_records(root.get("sources")),
    }

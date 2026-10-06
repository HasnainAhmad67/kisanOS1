"""PRD-aligned KisanOS Water Agent core.

This module is framework-independent and can run standalone or through the
FastAPI adapter. It uses farmer-confirmed field context and product-level,
fresh Weather Agent forecast metadata.

It never issues an irrigation command, uses days-since-irrigation/DAS/ET0/
temperature/rainfall thresholds, or treats a forecast as effective root-zone
recharge.
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from .schema import AgentOutput, validate_output


VERSION = "2.0.0"
AGENT_ID = "water"
POLICY_VERSION = "kisanos-water-conservative-v2"

SUPPORTED_AREAS = {
    "bahawalpur",
    "bahawalpur_sadar",
    "ahmadpur_east",
    "yazman",
    "hasilpur",
    "khairpur_tamewali",
}

AREA_LABELS = {
    "bahawalpur": "Bahawalpur",
    "bahawalpur_sadar": "Bahawalpur Sadar",
    "ahmadpur_east": "Ahmadpur East",
    "yazman": "Yazman",
    "hasilpur": "Hasilpur",
    "khairpur_tamewali": "Khairpur Tamewali",
}

VALID_STAGES = {
    "emergence",
    "cri",
    "tillering",
    "jointing",
    "booting",
    "heading",
    "flowering",
    "milk",
    "dough",
    "maturity",
}

STAGE_ALIASES = {
    "crown_root_initiation": "cri",
    "crown_root": "cri",
    "crown_root_stage": "cri",
    "germination": "emergence",
    "seedling": "emergence",
    "grain_filling": "milk",
}

VALID_SOIL_TEXTURES = {"sandy", "loamy", "clayey"}

ATTENTION_STATES = {
    "inspect_field",
    "monitor",
    "recheck_after_rain",
    "insufficient_information",
    "expert_review",
}

OPEN_METEO_DOCS_URL = "https://open-meteo.com/en/docs"

# Farmer-answerable field checks. Wording is fixed (i18n maps these exact
# strings) and every one of them is an observation task, never an irrigation
# instruction: no amount, timing, duration or schedule is derived from them.
CHECK_DRAINAGE = (
    "Inspect low spots and drainage paths; ask local extension staff to review "
    "persistent standing water or uncertain conditions."
)
CHECK_MOISTURE = (
    "Check soil moisture by hand at root depth in several representative spots "
    "and compare affected and healthy-looking areas."
)
CHECK_LAST_IRRIGATION = (
    "Write down the approximate date of the last irrigation you remember, "
    "so the record shows when water was last applied."
)
CHECK_GROWTH_STAGE = (
    "Confirm the wheat growth stage by looking at the plants if it is not recorded."
)
CHECK_PMD_UPDATE = (
    "Check the latest official PMD update and actual farm conditions; "
    "the stale or unavailable forecast is not used."
)
CHECK_AFTER_RAIN = (
    "After rainfall is actually observed, re-check root-zone soil moisture; "
    "do not treat the forecast as proof of recharge."
)
CHECK_CONFIRM_CONTEXT = (
    "Confirm stage and irrigation history locally; "
    "no timing or amount is calculated from these inputs."
)

MISSING_INPUTS_LABEL = "Missing inputs"

WATER_CONTEXT_LABELS = {
    "field_check_needed",
    "watch_drainage",
    "forecast_context_only",
}


def _utc_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(UTC)

    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    return current.astimezone(UTC).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _text(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value

    return str(value).strip().lower() if value is not None else ""


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        try:
            result = value.model_dump(mode="json")
        except TypeError:
            result = value.model_dump()

        return result if isinstance(result, dict) else {}

    return {}


def _float(
    value: Any,
    low: float | None = None,
    high: float | None = None,
) -> float | None:
    if isinstance(value, bool) or value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    if low is not None and number < low:
        return None

    if high is not None and number > high:
        return None

    return number


def _parse_timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        return _utc_iso(value)

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    return _utc_iso(parsed)


def _weather_payload(
    weather: Any,
) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    """Normalize dict or Pydantic weather responses."""

    root = _dict(weather)

    if not root and weather is not None:
        root = {
            "status": getattr(weather, "status", None),
            "data": getattr(weather, "data", None),
            "sources": getattr(weather, "sources", []),
            "weather_details": getattr(weather, "weather_details", None),
        }

    data = _dict(root.get("data"))

    if not data:
        data = _dict(root.get("weather_details"))

    providers = _dict(data.get("providers"))

    return data, providers, list(root.get("sources") or [])


def _product_status(panel: dict[str, Any]) -> str:
    value = _text(panel.get("status") or panel.get("weather_status"))

    if value.startswith("weather_"):
        value = value.removeprefix("weather_")

    return (
        value
        if value in {"fresh", "stale", "unavailable", "partial"}
        else "unavailable"
    )


def _forecast_context(weather: Any) -> dict[str, Any]:
    data, providers, sources = _weather_payload(weather)

    open_meteo = _dict(providers.get("open_meteo"))

    hourly_panel = _dict(open_meteo.get("hourly_72h"))
    daily_panel = _dict(open_meteo.get("daily_7d"))

    hourly_rows = hourly_panel.get("values")

    if not isinstance(hourly_rows, list):
        hourly_rows = data.get("hourly_next_72h")

    daily_rows = daily_panel.get("values")

    if not isinstance(daily_rows, list):
        daily_rows = data.get("daily_outlook_7d")

    hourly_status = _product_status(hourly_panel)
    daily_status = _product_status(daily_panel)

    aggregate = _text(
        data.get("weather_status") or data.get("freshness")
    )

    if hourly_status == "unavailable" and hourly_rows:
        if aggregate in {"fresh", "weather_fresh"}:
            hourly_status = "fresh"
        elif aggregate in {"stale", "weather_stale"}:
            hourly_status = "stale"

    if daily_status == "unavailable" and daily_rows:
        if aggregate in {"fresh", "weather_fresh"}:
            daily_status = "fresh"
        elif aggregate in {"stale", "weather_stale"}:
            daily_status = "stale"

    active_states: list[str] = []

    if isinstance(hourly_rows, list) and hourly_rows:
        active_states.append(hourly_status)

    if isinstance(daily_rows, list) and daily_rows:
        active_states.append(daily_status)

    if active_states and all(state == "fresh" for state in active_states):
        freshness = "fresh"
    elif any(state == "stale" for state in active_states):
        freshness = (
            "stale"
            if "fresh" not in active_states
            else "conflicting"
        )
    else:
        freshness = "unavailable"

    usable = freshness == "fresh"

    hourly_values = (
        [_dict(row) for row in (hourly_rows or [])]
        if usable
        else []
    )

    daily_values = (
        [_dict(row) for row in (daily_rows or [])]
        if usable
        else []
    )

    hourly_rain = [
        number
        for row in hourly_values
        if (
            number := _float(
                row.get("precipitation_mm"),
                0,
                2000,
            )
        )
        is not None
    ]

    hourly_probability = [
        number
        for row in hourly_values
        if (
            number := _float(
                row.get("precipitation_probability_pct"),
                0,
                100,
            )
        )
        is not None
    ]

    daily_rain = [
        number
        for row in daily_values
        if (
            number := _float(
                row.get("precipitation_sum_mm"),
                0,
                5000,
            )
        )
        is not None
    ]

    daily_probability = [
        number
        for row in daily_values
        if (
            number := _float(
                row.get("precipitation_probability_max_pct"),
                0,
                100,
            )
        )
        is not None
    ]

    precipitation_present = any(
        value > 0
        for value in (
            hourly_rain
            + hourly_probability
            + daily_rain
            + daily_probability
        )
    )

    retrieved_at = _parse_timestamp(
        hourly_panel.get("retrieved_at")
        or daily_panel.get("retrieved_at")
    )

    if not retrieved_at:
        for item in sources:
            source = _dict(item)

            publisher = _text(source.get("publisher"))

            if "open-meteo" in publisher:
                retrieved_at = _parse_timestamp(
                    source.get("retrieved_at")
                )

                if retrieved_at:
                    break

    return {
        "status": freshness,
        "provider": "Open-Meteo" if active_states else None,
        "forecast_horizon": "72-hour and seven-day products",
        "retrieved_at": retrieved_at,
        "precipitation_forecast_present": (
            precipitation_present if usable else None
        ),
        "maximum_hourly_precipitation_mm": (
            max(hourly_rain) if hourly_rain else None
        ),
        "maximum_hourly_precipitation_probability_pct": (
            max(hourly_probability)
            if hourly_probability
            else None
        ),
        "maximum_daily_precipitation_total_mm": (
            max(daily_rain) if daily_rain else None
        ),
        "maximum_daily_precipitation_probability_pct": (
            max(daily_probability)
            if daily_probability
            else None
        ),
        "probability_note": (
            "Precipitation probability is an event probability, "
            "not forecast confidence."
        ),
        "rainfall_recheck_is_not_recharge": True,
        "weather_product_statuses": {
            "hourly_72h": hourly_status,
            "daily_7d": daily_status,
        },
    }


def _source_records(
    weather: Any,
    freshness: str,
) -> list[dict[str, str]]:
    if freshness != "fresh":
        return []

    _data, _providers, sources = _weather_payload(weather)

    result: list[dict[str, str]] = []

    for item in sources:
        source = _dict(item)

        publisher = str(source.get("publisher") or "").strip()
        url = str(source.get("url") or "").strip()
        retrieved_at = _parse_timestamp(
            source.get("retrieved_at")
        )

        if (
            "open-meteo" not in publisher.lower()
            or not url.startswith(("https://", "http://"))
            or not retrieved_at
        ):
            continue

        result.append(
            {
                "title": str(
                    source.get("title")
                    or "Open-Meteo forecast data"
                ),
                "url": url,
                "publisher": publisher,
                "retrieved_at": retrieved_at,
                "source_status": str(
                    source.get("source_status")
                    or "official"
                ),
            }
        )

    return result[:2]


def _normalize_area(
    area: Any,
) -> tuple[str | None, str]:
    text = _text(area)

    key = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    ).strip("_")

    if key not in SUPPORTED_AREAS:
        return None, str(area or "").strip()

    return key, AREA_LABELS[key]


def _normal_stage(value: Any) -> str:
    stage = _text(value)

    stage = re.sub(
        r"[\s-]+",
        "_",
        stage,
    )

    stage = STAGE_ALIASES.get(
        stage,
        stage,
    )

    return (
        stage
        if stage in VALID_STAGES
        else "not_sure"
    )


def _valid_uuid(value: Any) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (
        ValueError,
        AttributeError,
        TypeError,
    ):
        return str(uuid.uuid4())


def _weather_context_state(status: str) -> str:
    """Map the forecast product state onto input_completeness.weather_context."""
    if status == "fresh":
        return "fresh"

    if status in {"stale", "conflicting"}:
        return "stale"

    return "unavailable"


def _prioritized_checks(
    *,
    drainage_known: bool,
    drainage_risk: bool,
    history_known: bool,
    stage_known: bool,
    weather_fresh: bool,
    rain_recheck_eligible: bool,
) -> list[str]:
    """Two or three prioritized, farmer-answerable checks.

    A drainage or saturation report is inspected first; otherwise the
    root-zone moisture check leads, followed by whichever inputs are
    actually missing, then the dated weather caveat. Nothing here ever
    states an irrigation amount, timing, duration or schedule.
    """
    checks: list[str] = []

    if drainage_risk:
        checks.append(CHECK_DRAINAGE)

    checks.append(CHECK_MOISTURE)

    if not history_known:
        checks.append(CHECK_LAST_IRRIGATION)

    if not drainage_known and not drainage_risk:
        checks.append(CHECK_DRAINAGE)

    if not stage_known:
        checks.append(CHECK_GROWTH_STAGE)

    if not weather_fresh:
        checks.append(CHECK_PMD_UPDATE)
    elif rain_recheck_eligible:
        checks.append(CHECK_AFTER_RAIN)
    else:
        checks.append(CHECK_CONFIRM_CONTEXT)

    return checks[:3]


def _reported_context_sentence(
    *,
    moisture: str,
    soil_texture: str,
    texture_known: bool,
    drainage: str,
    last_irrigation_date: Any,
    weather_fresh: bool,
) -> str:
    """Factual, non-directive summary of what the farmer reported."""
    soil = (
        f"{moisture} {soil_texture} soil"
        if texture_known
        else f"{moisture} soil"
    )
    drainage_phrase = {
        "good": "good drainage",
        "poor": "poor drainage",
        "waterlogging": "waterlogging",
    }.get(drainage, f"{drainage} drainage")

    sentence = (
        f"Farmer reports {soil}, {drainage_phrase}, "
        f"and last irrigation on {last_irrigation_date}."
    )

    if weather_fresh:
        sentence += " Weather forecast is context only."

    return sentence


def evaluate_water(
    intake: dict[str, Any],
    weather: Any = None,
    assessment_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate water context using conservative field-attention policy."""

    intake = (
        intake
        if isinstance(intake, dict)
        else {}
    )

    aid = _valid_uuid(
        assessment_id
        or intake.get("assessment_id")
    )

    created_at = _utc_iso()

    area_code, area_name = _normalize_area(
        intake.get("area_code")
        or intake.get("area")
    )

    crop = _text(
        intake.get("crop")
        or "wheat"
    )

    if crop not in {"wheat", "gandum"}:
        return _unavailable(
            aid,
            created_at,
            "Water Agent supports wheat only; "
            "no water assessment was made.",
            "Unsupported crop.",
        )

    if area_code is None:
        return _unavailable(
            aid,
            created_at,
            "Water context is unavailable because "
            "the area is outside the configured Bahawalpur pilot.",
            "Unsupported area; no location fallback was used.",
        )

    stage = _normal_stage(
        intake.get("growth_stage")
    )

    history_state = _text(
        intake.get("irrigation_history")
    )

    last_irrigation_date = intake.get(
        "last_irrigation_date"
    )

    history_known = (
        history_state == "known"
        and bool(last_irrigation_date)
    )

    moisture = _text(
        intake.get("soil_moisture")
    )

    drainage = _text(
        intake.get("drainage")
    )

    soil_texture = _text(
        intake.get("soil_texture")
    )

    sowing_date_supplied = bool(
        intake.get("sowing_date")
    )

    das_context_supplied = (
        intake.get("days_after_sowing")
        is not None
    )

    allowed_moisture = {
        "dry",
        "moist",
        "wet",
    }

    allowed_drainage = {
        "good",
        "poor",
        "waterlogging",
    }

    moisture_known = (
        moisture in allowed_moisture
    )

    drainage_known = (
        drainage in allowed_drainage
    )

    forecast = _forecast_context(weather)

    weather_fresh = (
        forecast["status"] == "fresh"
    )

    relevant_inputs_known = (
        stage in VALID_STAGES
        and history_known
        and moisture_known
        and drainage_known
    )

    # Structured completeness report: every field the farmer can state plus
    # the dated weather context. Unknown stays unknown - never inferred.
    input_completeness: dict[str, str] = {
        "growth_stage": "known" if stage in VALID_STAGES else "unknown",
        "irrigation_history": "known" if history_known else "unknown",
        "soil_texture": "known" if soil_texture in VALID_SOIL_TEXTURES else "unknown",
        "soil_moisture": "known" if moisture_known else "unknown",
        "drainage": "known" if drainage_known else "unknown",
        "weather_context": _weather_context_state(forecast["status"]),
    }

    missing: list[str] = []
    missing_inputs: list[str] = []

    if stage == "not_sure":
        missing.append("growth stage")
        missing_inputs.append("growth_stage")

    if not history_known:
        missing.append("last irrigation date")
        missing_inputs.append("last_irrigation_date")

    if not moisture_known:
        missing.append("soil moisture")
        missing_inputs.append("soil_moisture")

    if not drainage_known:
        missing.append("drainage condition")
        missing_inputs.append("drainage")

    if not weather_fresh:
        missing.append("fresh weather forecast")
        missing_inputs.append("fresh_weather_forecast")

    drainage_risk = (
        drainage in {"poor", "waterlogging"}
        or moisture == "wet"
    )

    flags = [
        "no_irrigation_command",
        "no_unapproved_numeric_thresholds",
        "forecast_not_effective_recharge",
    ]

    if not weather_fresh:
        flags.append(
            "weather_not_used_or_not_fresh"
        )

    if drainage_risk:
        flags.append(
            "drainage_or_saturation_inspection"
        )

    if not relevant_inputs_known:
        flags.append(
            "field_context_incomplete"
        )

    if (
        sowing_date_supplied
        or das_context_supplied
    ):
        flags.append(
            "sowing_context_recorded_not_used_as_threshold"
        )

    # Water-context label: drainage/saturation concern first, then any missing
    # or dry field input, otherwise the forecast is context only.
    if drainage_risk:
        water_context_label = "watch_drainage"
    elif moisture == "dry" or not relevant_inputs_known:
        water_context_label = "field_check_needed"
    else:
        water_context_label = "forecast_context_only"

    if water_context_label not in WATER_CONTEXT_LABELS:
        water_context_label = "field_check_needed"

    no_drainage_or_saturation_risk = (
        drainage == "good"
        and moisture != "wet"
    )

    forecast_rain = bool(
        forecast.get(
            "precipitation_forecast_present"
        )
    )

    rain_recheck_eligible = (
        weather_fresh
        and forecast_rain
        and no_drainage_or_saturation_risk
        and relevant_inputs_known
    )

    if (
        moisture == "wet"
        or drainage in {
            "poor",
            "waterlogging",
        }
    ):
        attention = "inspect_field"

        rationale = (
            "Reported wetness or drainage concern "
            "requires direct field inspection; "
            "weather cannot establish root-zone conditions."
        )

    elif moisture == "dry":
        attention = "inspect_field"

        rationale = (
            "Reported dry soil warrants a representative "
            "root-zone moisture check; this does not itself "
            "determine irrigation need."
        )

    elif missing:
        attention = "insufficient_information"

        rationale = (
            "Required stage, irrigation, soil, drainage, "
            "or fresh weather context is missing or uncertain."
        )

    elif stage == "cri":
        attention = "inspect_field"

        rationale = (
            "CRI is treated as a stage for closer inspection only; "
            "no regional schedule, date, or amount is inferred."
        )

    elif rain_recheck_eligible:
        attention = "recheck_after_rain"

        rationale = (
            "A fresh forecast indicates possible precipitation; "
            "re-check soil moisture only after rain is actually observed."
        )

    else:
        attention = "monitor"

        rationale = (
            "Available context supports monitoring and direct field "
            "checks only; no irrigation schedule or command is inferred."
        )

    if attention not in ATTENTION_STATES:
        attention = "insufficient_information"

    status = (
        "complete"
        if relevant_inputs_known and weather_fresh
        else "partial"
    )

    evidence_band = (
        "low"
        if status == "complete"
        else "not_calibrated"
    )

    observations = [
        f"Farmer-confirmed pilot area: {area_name}."
    ]

    if stage != "not_sure":
        observations.append(
            f"Farmer-selected wheat growth stage: {stage}."
        )
    else:
        observations.append(
            "Wheat growth stage is marked not sure."
        )

    if history_known:
        observations.append(
            "Farmer-provided last irrigation date: "
            f"{last_irrigation_date}."
        )
    else:
        observations.append(
            "Last irrigation history is missing or marked not sure."
        )

    if moisture_known:
        observations.append(
            f"Farmer-reported soil moisture: {moisture}; "
            "it is not sensor-measured."
        )
    else:
        observations.append(
            "Soil moisture is missing or marked not sure."
        )

    if drainage_known:
        observations.append(
            f"Farmer-reported drainage condition: {drainage}; "
            "it is not independently verified."
        )
    else:
        observations.append(
            "Drainage condition is missing or marked not sure."
        )

    if soil_texture in VALID_SOIL_TEXTURES:
        observations.append(
            f"Farmer-reported soil texture: {soil_texture}; "
            "retained as context only, not as an action threshold."
        )

    if (
        sowing_date_supplied
        or das_context_supplied
    ):
        observations.append(
            "Farmer-provided sowing-date or DAS context is retained "
            "for transparency and is not used to trigger an action threshold."
        )

    if weather_fresh:
        if forecast_rain:
            observations.append(
                "Fresh Open-Meteo forecast products indicate possible "
                "precipitation; the forecast does not confirm effective "
                "root-zone recharge."
            )
        else:
            observations.append(
                "Fresh Open-Meteo forecast products contain no positive "
                "precipitation amount or probability in the returned periods."
            )

        observations.append(
            "Weather is used as dated context only, not as a "
            "soil-moisture measurement or irrigation threshold."
        )

    elif forecast["status"] in {
        "stale",
        "conflicting",
    }:
        observations.append(
            "Weather forecast data are stale or conflicting "
            "and were not used for a water decision."
        )

    else:
        observations.append(
            "No usable fresh forecast was available; "
            "weather was not used to infer water need."
        )

    causes: list[str] = []

    if moisture == "dry":
        causes.append(
            "Farmer-reported dry soil is a possible water-context "
            "concern; it is not independently measured and does not "
            "establish a crop-symptom cause."
        )

    if (
        moisture == "wet"
        or drainage in {
            "poor",
            "waterlogging",
        }
    ):
        causes.append(
            "Farmer-reported wetness or poor drainage may indicate "
            "a saturation concern; field conditions require direct verification."
        )

    if forecast_rain and weather_fresh:
        causes.append(
            "Forecast precipitation is context only and does not "
            "establish effective root-zone recharge or a cause of crop symptoms."
        )

    checks = _prioritized_checks(
        drainage_known=drainage_known,
        drainage_risk=drainage_risk,
        history_known=history_known,
        stage_known=stage in VALID_STAGES,
        weather_fresh=weather_fresh,
        rain_recheck_eligible=rain_recheck_eligible,
    )

    sources = _source_records(
        weather,
        forecast["status"],
    )

    if not sources and weather_fresh:
        flags.append(
            "weather_provenance_missing"
        )

    reason = (
        "Conservative field-attention policy using farmer-reported "
        "stage, irrigation date, soil and drainage context plus fresh, "
        "source-labeled weather products. No local threshold set is approved; "
        "no irrigation amount, timing, frequency, or command is generated."
        if status == "complete"
        else
        "Evidence is incomplete or weather is not fresh. Unknown values "
        "remain unknown; use direct field checks. No locally unapproved "
        "numeric threshold or irrigation command is used."
    )

    # Summary: name exactly what is missing, or state what was reported.
    summary_parts: list[str] = []

    if missing:
        summary_parts.append(f"{MISSING_INPUTS_LABEL}: {', '.join(missing)}.")
    else:
        summary_parts.append(
            _reported_context_sentence(
                moisture=moisture,
                soil_texture=soil_texture,
                texture_known=soil_texture in VALID_SOIL_TEXTURES,
                drainage=drainage,
                last_irrigation_date=last_irrigation_date,
                weather_fresh=weather_fresh,
            )
        )

    if attention != "insufficient_information":
        summary_parts.append(rationale)

    summary_parts.append(
        "Only direct soil and drainage checks can establish current "
        "field conditions; no irrigation command, amount, or schedule is provided."
    )

    summary = f"Water attention: {attention}. " + " ".join(summary_parts)

    return {
        "agent_id": AGENT_ID,
        "assessment_id": aid,
        "status": status,
        "summary": summary,
        "observations": observations,
        "possible_causes": causes,
        "checks": checks[:3],
        "evidence_band": evidence_band,
        "evidence_reason": reason,
        "sources": sources,
        "provider_or_model": "self-hosted",
        "version": VERSION,
        "created_at": created_at,
        "safety_flags": flags,

        "backend_data": {
            "water_attention": attention,
            "policy_version": POLICY_VERSION,
            "irrigation_command": None,
            "input_completeness": input_completeness,
            "missing_inputs": missing_inputs,
            "water_context": {
                **forecast,
                "label": water_context_label,
                "rain_recheck_eligible": rain_recheck_eligible,
                "used_for_numeric_thresholds": False,
            },
        },

        "input_evidence": [
            f"Confirmed wheat pilot area: {area_name}",
            f"Growth stage: {stage}",
            f"Irrigation history known: {history_known}",
            f"Soil moisture: "
            f"{moisture if moisture_known else 'not_sure'}",
            f"Drainage: "
            f"{drainage if drainage_known else 'not_sure'}",
            f"Soil texture: "
            f"{soil_texture if soil_texture in VALID_SOIL_TEXTURES else 'not_sure'}",
            f"Sowing-date context supplied: {sowing_date_supplied}",
            f"DAS context supplied: {das_context_supplied}",
        ],
    }


def _unavailable(
    assessment_id: str,
    created_at: str,
    summary: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "agent_id": AGENT_ID,
        "assessment_id": assessment_id,
        "status": "unavailable",
        "summary": (
            f"{summary} "
            "No irrigation command, amount, or schedule is produced."
        ),
        "observations": [],
        "possible_causes": [],
        "checks": [
            "Confirm wheat crop and select a supported Bahawalpur "
            "pilot area before reassessment."
        ],
        "evidence_band": "not_calibrated",
        "evidence_reason": reason,
        "sources": [],
        "provider_or_model": "self-hosted",
        "version": VERSION,
        "created_at": created_at,
        "safety_flags": [
            "unsupported_scope",
            "no_irrigation_command",
        ],
        "backend_data": {
            "water_attention": "insufficient_information",
            "policy_version": POLICY_VERSION,
            "irrigation_command": None,
            "water_context": {
                "status": "unavailable",
                "used_for_numeric_thresholds": False,
            },
        },
        "input_evidence": [],
    }


def analyze_water(
    crop: Any = "wheat",
    area: Any = "bahawalpur_sadar",
    last_irrigation_days: Any = None,
    growth_stage: Any = "not_sure",
    days_after_sowing: Any = None,
    weather: Any = None,
    soil_moisture: Any = "not_sure",
    enhance: bool = False,
    use_llm: bool = False,
    assessment_id: str | None = None,
    *,
    irrigation_history: Any = "not_sure",
    last_irrigation_date: Any = None,
    drainage: Any = "not_sure",
    sowing_date: Any = None,
    soil_texture: Any = "not_sure",
) -> dict[str, Any]:
    """Standalone entry point returning the common agent envelope."""

    aid = _valid_uuid(assessment_id)

    intake = {
        "crop": crop,
        "area": area,
        "growth_stage": growth_stage,
        "irrigation_history": irrigation_history,
        "last_irrigation_date": last_irrigation_date,
        "soil_moisture": soil_moisture,
        "drainage": drainage,
        "sowing_date": sowing_date,
        "soil_texture": soil_texture,
        "days_after_sowing": days_after_sowing,
    }

    try:
        decision = evaluate_water(
            intake,
            weather=weather,
            assessment_id=aid,
        )

        common_fields = set(
            AgentOutput.model_fields
        )

        output = {
            key: value
            for key, value in decision.items()
            if key in common_fields
            and key != "AI_ENHANCED"
        }

        validated = (
            AgentOutput.model_validate(output)
            .model_dump(
                mode="json",
                exclude_none=True,
            )
        )

        problems = validate_output(validated)

        if problems:
            raise ValueError(
                "; ".join(problems[:3])
            )

        return validated

    except (
        ValidationError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ):
        safe = _unavailable(
            aid,
            _utc_iso(),
            "Water assessment could not be validated.",
            "Internal validation error; no assessment was made.",
        )

        common_fields = set(
            AgentOutput.model_fields
        )

        return (
            AgentOutput.model_validate(
                {
                    key: value
                    for key, value in safe.items()
                    if key in common_fields
                }
            )
            .model_dump(
                mode="json",
                exclude_none=True,
            )
        )


def get_water_attention(
    result: dict[str, Any],
) -> str | None:
    """Read the PRD attention state from a backend result summary."""

    summary = str(
        (result or {}).get(
            "summary",
            "",
        )
    )

    match = re.match(
        r"Water attention: ([a-z_]+)\.",
        summary,
    )

    return (
        match.group(1)
        if match
        and match.group(1) in ATTENTION_STATES
        else None
    )


get_irrigation_status = get_water_attention
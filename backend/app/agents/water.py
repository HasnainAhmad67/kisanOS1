from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas import AgentResult, Source

VERSION = "water-safe-policy-1.0.0"


def assess_water(assessment_id: str, intake: dict[str, Any], weather: AgentResult | None = None) -> AgentResult:
    stage = intake.get("growth_stage", "not_sure")
    moisture = intake.get("soil_moisture", "not_sure")
    drainage = intake.get("drainage", "not_sure")
    known_irrigation = intake.get("irrigation_history") == "known" and bool(intake.get("last_irrigation_date"))
    input_evidence = [
        f"Farmer-selected growth stage: {stage}",
        f"Farmer-reported soil moisture: {moisture}",
        f"Farmer-reported drainage: {drainage}",
    ]
    checks: list[str] = []
    observations: list[str] = []
    status = "partial"
    band = "low"
    flags = ["no_irrigation_instruction", "unvalidated_numeric_thresholds_excluded"]
    if moisture == "wet" or drainage in {"poor", "waterlogging"}:
        summary = "Waterlogging or wet soil was reported; inspect field drainage and soil condition. No irrigation need is inferred."
        observations.append("Farmer-reported wet soil or drainage concern.")
        checks.append(
            "Inspect low spots and drainage paths; compare soil condition in affected and unaffected parts of the field."
        )
        checks.append(
            "Ask a local agriculture officer to review persistent standing water or uncertain field conditions."
        )
        status = "complete"
    elif moisture == "dry":
        summary = "Dry surface/root-zone conditions were reported; verify soil moisture in more than one representative spot before deciding what to do."
        observations.append("Farmer-reported dry soil; this report has not been independently measured.")
        checks.append(
            "Check soil at root depth in several representative spots and compare affected and healthy-looking areas."
        )
        status = "complete"
    elif stage == "cri":
        summary = "Crown root initiation (CRI) was selected. Regional guidance treats this as a stage to pay attention to, but no Bahawalpur schedule is inferred."
        observations.append("Farmer-selected CRI stage; stage has not been independently verified.")
        checks.append(
            "Check root-zone soil moisture in representative spots and confirm stage-specific decisions with local extension guidance."
        )
        sources = [
            Source(
                title="Regional wheat-stage context (not a Bahawalpur schedule)",
                url="https://agri.sindh.gov.pk/irrigation",
                publisher="Government of Sindh, Agriculture Department",
                geography="Sindh; supporting context only, not a Bahawalpur rule",
                source_status="supporting",
                note="Not used to infer timing, amount, or frequency.",
            )
        ]
        status = "complete"
        return _result(assessment_id, summary, observations, checks, status, band, flags, input_evidence, sources)
    elif not known_irrigation or stage == "not_sure" or moisture == "not_sure":
        summary = "Key water-context information is uncertain; no irrigation status is inferred."
        checks.append(
            "If convenient, confirm the crop stage and check soil moisture by hand in representative parts of the field."
        )
        checks.append("Record the last irrigation date if known; otherwise keep it marked as not sure.")
    else:
        summary = "No immediate water conclusion is drawn from the supplied context; continue field monitoring."
        checks.append("Check soil moisture in representative spots before making any field water decision.")
        status = "complete"
        band = "low"
    if weather is None or weather.status in {"unavailable", "stale", "error"}:
        observations.append("No usable fresh weather evidence was available; weather was not used to infer water need.")
        flags.append("weather_not_used")
    else:
        observations.append(
            "Weather information is contextual only and is not a field-level soil-moisture measurement."
        )
        input_evidence.append("Weather source available; not used as a water threshold")
    sources = []
    if weather and weather.status == "complete":
        sources.extend(weather.sources)
    return _result(assessment_id, summary, observations, checks, status, band, flags, input_evidence, sources)


def _result(
    assessment_id: str,
    summary: str,
    observations: list[str],
    checks: list[str],
    status: str,
    band: str,
    flags: list[str],
    inputs: list[str],
    sources: list[Source],
) -> AgentResult:
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="water",
        status=status,
        summary=summary,
        observations=observations,
        possible_causes=[],
        checks=checks[:3],
        evidence_band=band,
        evidence_reason="Conservative field-attention policy; unknowns remain unknown. Exact day, rainfall, temperature, evapotranspiration, depth, and interval thresholds are disabled pending local agronomist review.",
        sources=sources,
        provider_or_model="deterministic-policy; supplied water agent threshold rules quarantined",
        version=VERSION,
        created_at=datetime.now(UTC),
        safety_flags=flags,
        data={
            "water_attention": "inspect_field" if status == "complete" else "insufficient_information",
            "irrigation_command": None,
        },
        input_evidence=inputs,
    )

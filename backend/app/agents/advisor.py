from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.schemas import AgentResult, FarmCheck, FarmPlan

SAFETY_BANNER = (
    "This is screening and decision support, not a confirmed diagnosis. Do not apply chemicals based only on an image. "
    "For severe, spreading, or unclear symptoms, consult a local agriculture officer or qualified expert."
)


def build_farm_plan(assessment_id: str, intake: dict[str, Any], agents: list[AgentResult]) -> FarmPlan:
    by_id = {item.agent_id: item for item in agents}
    crop = by_id.get("crop")
    water = by_id.get("water")
    vision = by_id.get("vision")
    meaningful_crop = bool(crop and crop.observations and crop.status in {"complete", "partial"})
    unknown_context = intake.get("growth_stage") == "not_sure" or intake.get("irrigation_history") == "not_sure"
    spreading = intake.get("symptoms_spreading") == "yes"
    crop_text = " ".join((crop.observations if crop else []) + (crop.possible_causes if crop else [])).lower()
    rust_like = "rust-like" in crop_text or "pustule" in crop_text
    referral = spreading or rust_like or bool(crop and crop.data.get("referral_recommended"))

    conflicts: list[dict[str, Any]] = []
    moisture = intake.get("soil_moisture", "not_sure")
    dry_symptom = any(word in crop_text for word in ("yellow", "drying", "wilting", "water stress"))
    if moisture == "wet" and dry_symptom:
        conflicts.append(
            {
                "topic": "field_moisture",
                "findings": [
                    "Farmer reports wet soil or drainage concern",
                    "Crop Agent identified signs that can overlap with water stress",
                ],
                "next_check": "Compare root-zone moisture in affected and unaffected spots; wet soil does not rule out other causes.",
            }
        )
    weather = by_id.get("weather")
    if weather and weather.status == "stale":
        conflicts.append(
            {
                "topic": "weather_freshness",
                "findings": ["Weather provider timestamp is stale or missing"],
                "next_check": "Do not use this weather result for a field decision; continue with direct field checks.",
            }
        )

    candidates: list[tuple[str, str, str, list[str]]] = []
    if crop:
        for idx, check in enumerate(crop.checks):
            candidates.append(
                (
                    check,
                    "Crop",
                    "Farmer-reported and/or photo-visible evidence; possibilities remain unconfirmed.",
                    ["crop"],
                )
            )
    if water:
        for check in water.checks:
            candidates.append(
                (
                    check,
                    "Water",
                    "Conservative soil and drainage check; no irrigation schedule or command is inferred.",
                    ["water"],
                )
            )
    if vision and vision.status in {"complete", "partial"}:
        for check in vision.checks:
            candidates.append(
                (check, "Vision", "Image evidence is limited to visible signs and cannot confirm cause.", ["vision"])
            )
    if not candidates:
        candidates = [
            (
                "Describe which plant part looks different and compare several plants with a healthy-looking area.",
                "Farm Advisor",
                "There is not enough evidence to distinguish a cause.",
                ["farmer_reported"],
            )
        ]

    chosen: list[FarmCheck] = []
    seen = set()
    for title, source, why, labels in candidates:
        normalized = title.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        chosen.append(
            FarmCheck(
                id=f"check-{len(chosen) + 1}",
                priority=len(chosen) + 1,
                title=title[:260],
                how_to_check=title[:260],
                why=why,
                evidence_labels=labels,
            )
        )
        if len(chosen) == 3:
            break

    if referral:
        status = "expert_review_recommended"
        rationale = "Spreading, rust-like, severe, or unclear symptoms merit review by a qualified local expert; the system does not identify a confirmed cause."
    elif not meaningful_crop and (unknown_context or not intake.get("symptoms")):
        status = "insufficient_information"
        rationale = "Key field or symptom information is missing or uncertain; the system does not infer a normal/abnormal verdict."
    elif meaningful_crop or (water and water.status == "complete"):
        status = "field_inspection_recommended"
        rationale = "Available reports support a small set of direct field checks; they do not establish a cause or prescribe an action."
    else:
        status = "monitor"
        rationale = "Continue observing the field and update the assessment if signs change."

    agent_summary = {item.agent_id: item.summary for item in agents}
    return FarmPlan(
        status=status,
        rationale=rationale,
        agent_summary=agent_summary,
        checks=chosen,
        verification_step="Record what you observed after checking; if signs spread, remain unclear, or appear severe, ask a local agriculture officer to review them.",
        conflicts=conflicts,
        safety_banner=SAFETY_BANNER,
        policy_version=get_settings().policy_version,
        created_at=datetime.now(UTC),
    )

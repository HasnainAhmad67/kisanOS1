from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.text_guard import find_unsafe
from app.schemas import AgentResult, FarmCheck, FarmPlan

SAFETY_BANNER = (
    "This is screening and decision support, not a confirmed diagnosis. Do not apply chemicals based only on an image. "
    "For severe, spreading, or unclear symptoms, consult a local agriculture officer or qualified expert."
)

# Statuses that count as an actual assessment: their checks and referral flags
# may be used. unavailable / stale / not_assessed / error cards never become
# findings (A4) and never contribute checks.
_CONTRIBUTING = frozenset({"complete", "partial"})
# Crop may also use its deliberate wheat-scope abstention ("unsupported").
_CROP_USABLE = frozenset({"complete", "partial", "unsupported"})

_HOW_TO_CHECK = {
    "Crop": (
        "Repeat the check on several plants in the affected area and on one "
        "healthy-looking area for comparison."
    ),
    "Water": (
        "Check the same spots by hand at root depth and compare the affected "
        "and unaffected areas."
    ),
    "Vision": (
        "Look at the plant part described in the report and compare it with a "
        "healthy-looking plant."
    ),
    "Farm Advisor": (
        "Describe the plant part and compare several plants with a healthy-looking area."
    ),
}
WHAT_TO_OBSERVE = (
    "What you actually see at each spot, whether it looks the same on plants that look "
    "healthy, and whether it changes between checks."
)

_FUNCTION_WORDS = frozenset(
    {
        "about", "after", "again", "against", "because", "before", "being", "between",
        "both", "does", "doing", "down", "each", "from", "have", "having", "here",
        "into", "itself", "more", "most", "other", "over", "same", "should", "some",
        "such", "than", "that", "their", "them", "then", "there", "these", "they",
        "this", "those", "through", "under", "until", "very", "were", "what", "when",
        "where", "which", "while", "with", "would", "your", "been", "also", "only",
        "looks", "look", "note",
    }
)


def _tokens(text: str) -> set[str]:
    """Content words (4+ letters) of a lowercase text, minus function words."""
    return {
        word
        for word in re.findall(r"[a-z]{4,}", text.casefold())
        if word not in _FUNCTION_WORDS
    }


def _crop_vision_disagree(crop: AgentResult, vision: AgentResult) -> bool:
    """True when both cards are meaningful but share no content word.

    A vision card that returned no supported finding is not a disagreement,
    and an empty side never counts as one either.
    """
    if vision.observations == ["The model did not return a supported visible finding."]:
        return False
    crop_words = _tokens(" ".join(crop.observations + crop.possible_causes))
    vision_words = _tokens(" ".join(vision.observations))
    if not crop_words or not vision_words:
        return False
    return not (crop_words & vision_words)


def build_farm_plan(assessment_id: str, intake: dict[str, Any], agents: list[AgentResult]) -> FarmPlan:
    """Deterministic plan from validated card envelopes only.

    The status ladder is expert_review_recommended >
    insufficient_information > field_inspection_recommended > monitor.
    Conflicts are appended, never reconciled: disagreement stays visible.
    No new agronomic fact is generated here - checks come from the agents'
    own non-chemical check text and are screened again as defense in depth.
    """
    by_id = {item.agent_id: item for item in agents}
    crop = by_id.get("crop")
    water = by_id.get("water")
    vision = by_id.get("vision")
    weather = by_id.get("weather")

    crop_usable = bool(crop and crop.status in _CROP_USABLE)
    crop_meaningful = bool(crop and crop.status in _CONTRIBUTING and crop.observations)
    water_ok = bool(water and water.status in _CONTRIBUTING)
    vision_ok = bool(vision and vision.status in _CONTRIBUTING)
    weather_ok = bool(weather and weather.status in _CONTRIBUTING)

    unknown_context = intake.get("growth_stage") == "not_sure" or intake.get("irrigation_history") == "not_sure"
    spreading = intake.get("symptoms_spreading") == "yes"
    crop_text = (
        " ".join((crop.observations if crop else []) + (crop.possible_causes if crop else [])).lower()
        if crop_usable
        else ""
    )
    rust_like = "rust-like" in crop_text or "pustule" in crop_text

    # Referral flags (A2): only cards that actually assessed may escalate, and
    # escalation stays conservative - it names no cause.
    crop_referral = bool(
        crop and crop.status in _CROP_USABLE and isinstance(crop.data, dict)
        and crop.data.get("referral_recommended")
    )
    water_attention = (
        water.data.get("water_attention") if water and isinstance(water.data, dict) else None
    )
    water_referral = bool(water_ok and water_attention == "expert_review")
    water_insufficient = bool(water_ok and water_attention == "insufficient_information")
    referral = spreading or rust_like or crop_referral or water_referral

    # ---- Conflicts: surfaced, never forced into consensus (C1-C3) ----
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

    precipitation: float | None = None
    if weather_ok and isinstance(weather.data, dict):
        current = weather.data.get("current")
        if isinstance(current, dict):
            raw = current.get("precipitation_mm")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                precipitation = float(raw)
    if weather_ok and moisture == "dry" and precipitation is not None and precipitation > 0:
        conflicts.append(
            {
                "topic": "field_moisture_vs_weather",
                "findings": [
                    "Farmer reports dry soil at the observed time",
                    f"Weather provider recorded {precipitation:g} mm precipitation at the forecast-grid location",
                ],
                "next_check": "Compare the observation time with the weather timestamp and re-check soil moisture by hand at root depth in affected and unaffected spots.",
            }
        )

    if weather and weather.status == "stale":
        conflicts.append(
            {
                "topic": "weather_freshness",
                "findings": ["Weather provider timestamp is stale or missing"],
                "next_check": "Do not use this weather result for a field decision; continue with direct field checks.",
            }
        )

    if crop and vision and crop_meaningful and vision_ok and _crop_vision_disagree(crop, vision):
        conflicts.append(
            {
                "topic": "crop_vision_disagreement",
                "findings": [
                    "Crop Agent evidence: "
                    + "; ".join((crop.observations + crop.possible_causes)[:3])[:220],
                    "Vision Agent visible signs: " + "; ".join(vision.observations[:3])[:220],
                ],
                "next_check": "Compare the photo-visible signs with what you reported in the field on several plants, and ask a local agriculture officer to review anything that keeps disagreeing.",
            }
        )

    # ---- Checks: prioritized crop -> water -> vision, capped at 3, deduped ----
    candidates: list[tuple[str, str, str, list[str]]] = []
    if crop and crop.status in _CROP_USABLE:
        for check in crop.checks:
            candidates.append(
                (
                    check,
                    "Crop",
                    "Farmer-reported and/or photo-visible evidence; possibilities remain unconfirmed.",
                    ["crop"],
                )
            )
    if water and water_ok:
        for check in water.checks:
            candidates.append(
                (
                    check,
                    "Water",
                    "Conservative soil and drainage check; no irrigation schedule or command is inferred.",
                    ["water"],
                )
            )
    if vision and vision_ok:
        for check in vision.checks:
            candidates.append(
                (check, "Vision", "Image evidence is limited to visible signs and cannot confirm cause.", ["vision"])
            )
    if vision and vision_ok and "low_quality_image" in (vision.safety_flags or []):
        # Low-quality photo: surface the retake recommendation first so it is
        # not pushed out when other checks fill the top-3. (Dedup keeps the
        # later copy of the same title from being chosen twice.)
        retake = next((c for c in vision.checks if c.casefold().startswith("retake")), None)
        if retake:
            candidates.insert(
                0,
                (retake, "Vision", "The photo was low-quality; the visible-sign check is low-confidence only.", ["vision"]),
            )

    # Defense in depth (B5/D2): never surface chemical, dosing, imperative
    # irrigation, diagnosis-claim, guarantee or trading wording.
    candidates = [item for item in candidates if not find_unsafe(item[0])]

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
    seen: set[str] = set()
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
                how_to_check=_HOW_TO_CHECK.get(source, _HOW_TO_CHECK["Farm Advisor"]),
                why=why,
                what_to_observe=WHAT_TO_OBSERVE,
                evidence_labels=labels,
            )
        )
        if len(chosen) == 3:
            break

    # ---- Status ladder (A1): expert > insufficient > field_inspection > monitor ----
    if referral:
        status = "expert_review_recommended"
        rationale = "Spreading, rust-like, severe, or unclear symptoms merit review by a qualified local expert; the system does not identify a confirmed cause."
    elif water_insufficient or (not crop_meaningful and (unknown_context or not intake.get("symptoms"))):
        status = "insufficient_information"
        rationale = "Key field or symptom information is missing or uncertain; the system does not infer a normal/abnormal verdict."
    elif crop_meaningful or (water and water.status == "complete"):
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

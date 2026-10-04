"""Deterministic, PRD-aligned Crop Agent for the Bahawalpur wheat pilot.

Screening only. This module turns farmer-reported symptoms and (optionally)
Vision Agent visible observations into hypothesis language plus farmer-
answerable, non-chemical field checks. It never names a confirmed disease,
never recommends a product, dose, or spray schedule, and never issues an
irrigation command.

Evidence handling (kept separate and explicitly labelled):
- farmer_reported: symptom tags chosen by the farmer, labelled as reports.
- photo_visible: Vision observations, used only when Vision status is
  "complete" or "partial"; never treated as a confirmed diagnosis. If Vision
  is unavailable, stale, not_assessed, erro, or has no useful observations,
  Crop continues on farmer-reported symptoms only.
- rule_based_check: deterministic checks derived from those two classes.

Expert-review referral triggers (recorded in data["referral_reasons"]):
- rust-like pustules reported or observed
- symptoms rapidly spreading
- heading-to-grain growth stage with symptom evidence
- cause remains unknown
- evidence is low or conflicting
- farmer asks about a chemical/treatment

Sources: the source registry has no externally verified Crop agronomy record,
so this card ships with sources=[] and every rule is explicitly marked
unverified/provisional (registry id: crop-rules). No model, dataset, or
external service is required or used.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.schemas import AgentResult

VERSION = "crop-rules-1.1.0"
SOURCE_REGISTRY_ID = "crop-rules"

SYMPTOM_LABELS = {
    "yellowing": "visible yellowing reported by the farmer",
    "spots": "spots or blotches reported by the farmer",
    "rust_like": "rust-like marks reported by the farmer",
    "wilting": "wilting or leaf rolling reported by the farmer",
    "drying": "premature drying reported by the farmer",
    "insects": "visible insects reported by the farmer",
    "mildew_like": "mildew-like appearance reported by the farmer",
    "lodging": "lodging reported by the farmer",
    "unknown": "the farmer is unsure what the symptom may be",
}

# Growth stages from heading through grain filling; significant symptoms at
# these stages go to expert review rather than being screened further here.
_HEADING_TO_GRAIN_STAGES = {"heading", "flowering", "milk", "dough"}

# Free-answer words (English/Urdu romanised + Urdu script) indicating the
# farmer is asking about chemical treatment. Scanned for referral only and
# never echoed back into the result.
_CHEMICAL_QUESTION = re.compile(
    r"\b(spray|spraying|pesticide|pesticides|fungicide|fungicides|insecticide|"
    r"insecticides|herbicide|herbicides|dose|doses|dosage|urea|dap|npk|fertilizer|"
    r"fertiliser|fertilizers|fertilisers|medicine|dawa|dawai|khaad|khad|keera\s?maar|"
    r"keeray\s?maar)\b"
    r"|کیڑے\s?مار|سپرے|کھاد|زرعی\s?دوا|دوائی|ڈوز",
    re.IGNORECASE,
)

_WATER_KEYS = ("yellow", "wilt", "roll")
_DRYING_KEYS = ("dry",)
_SPOT_KEYS = ("spot", "pustule", "rust")
_INSECT_KEYS = ("insect", "aphid", "hole", "chew")

_REFERRAL_NOTE = (
    "Ask a local agriculture officer or qualified expert to review spreading, "
    "rust-like, severe, or unclear symptoms and any treatment question before "
    "any action."
)

_UNVERIFIED_REASON = (
    "Crop screening rules are provisional and unverified: the source registry "
    f"holds no externally verified Crop agronomy source record (registry id: {SOURCE_REGISTRY_ID})."
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(v) for v in value)
    if isinstance(value, dict):
        return " ".join(f"{_text(k)} {_text(v)}" for k, v in value.items())
    return str(value)


def _has_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(n in haystack for n in needles)


def _vision_parts(vision: Any) -> tuple[str, list[str]]:
    """Return (vision status, usable photo observations).

    Observations are only usable when Vision status is complete or partial.
    Everything else (unavailable, stale, not_assessed, error, empty) yields
    no photo evidence so Crop continues on farmer-reported symptoms alone.
    """
    if vision is None:
        return "absent", []
    if isinstance(vision, dict):
        status = _text(vision.get("status")) or "absent"
        raw_obs = vision.get("observations") or []
    else:
        status = _text(getattr(vision, "status", None)) or "absent"
        raw_obs = getattr(vision, "observations", None) or []
    if status not in {"complete", "partial"}:
        return status, []
    if isinstance(raw_obs, dict):
        return status, []
    photo: list[str] = []
    for obs in raw_obs:
        obs_text = _text(obs).strip()
        if obs_text:
            photo.append(obs_text)
        if len(photo) >= 4:
            break
    return status, photo


def _unsupported(assessment_id: str, crop_name: str) -> AgentResult:
    """Wheat-only scope guard: abstain instead of screening other crops."""
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="crop",
        status="unsupported",
        summary="The Crop Agent supports wheat only; no crop assessment was made for this crop.",
        observations=[],
        possible_causes=[],
        checks=[
            "Select wheat, or ask a local agriculture expert about this crop.",
        ],
        evidence_band="not_calibrated",
        evidence_reason=(
            "Unsupported crop scope: no rule was applied and no cause was assessed. "
            + _UNVERIFIED_REASON
        ),
        sources=[],
        provider_or_model="deterministic-wheat-screening-rules",
        version=VERSION,
        created_at=datetime.now(UTC),
        safety_flags=["unsupported_scope", "not_a_diagnosis", "crop_rules_unverified"],
        data={
            "referral_recommended": True,
            "referral_reasons": ["unsupported_crop_scope"],
            "supported_crop": "wheat",
            "vision_used": False,
            "vision_status": "not_applicable",
            "evidence_labels": {
                "farmer_reported": [],
                "photo_visible": [],
                "rule_based_check": [],
            },
            "rule_verification": {
                "status": "unverified",
                "source_registry_id": SOURCE_REGISTRY_ID,
                "note": _UNVERIFIED_REASON,
            },
        },
        input_evidence=[f"crop_scope: reported crop '{crop_name}' is outside the supported wheat scope"],
    )


def assess_crop(assessment_id: str, intake: dict[str, Any], vision: AgentResult | None) -> AgentResult:
    intake = intake if isinstance(intake, dict) else {}

    crop_name = _text(intake.get("crop")).strip().lower()
    if crop_name not in {"wheat", "gandum"}:
        # Abstain rather than silently fall back (PRD: unsupported crop does
        # not silently fall back). Missing/unknown crop is unsupported too.
        return _unsupported(assessment_id, crop_name or "(not provided)")

    # ------------------------------------------------------------------
    # Evidence: farmer-reported and photo-visible kept separate.
    # ------------------------------------------------------------------
    raw_value = intake.get("symptoms") or []
    if isinstance(raw_value, str):
        raw_value = [raw_value]
    raw_symptoms = [_text(s).strip() for s in raw_value]
    raw_symptoms = [s for s in raw_symptoms if s]
    reported_tags = [t for t in raw_symptoms if t in SYMPTOM_LABELS]
    farmer_evidence = [SYMPTOM_LABELS[t] for t in reported_tags]
    vision_status, photo_evidence = _vision_parts(vision)
    if isinstance(vision, dict):
        vision_flags = vision.get("safety_flags") or []
    else:
        vision_flags = getattr(vision, "safety_flags", None) or []

    combined = " ".join(farmer_evidence + photo_evidence).lower()
    has_evidence = bool(farmer_evidence or photo_evidence)
    band = "medium" if (farmer_evidence and photo_evidence) else "low"
    if "low_quality_image" in vision_flags:
        # Soft-warning Vision output is consumed as photo_visible but stays
        # low evidence: never confirmation, farmer-reported symptoms remain
        # primary, and the band is never lifted to medium.
        band = "low"

    # ------------------------------------------------------------------
    # Hypotheses (never probabilities, never confirmed diagnoses).
    # ------------------------------------------------------------------
    hypotheses: list[str] = []
    if _has_any(combined, _WATER_KEYS):
        hypotheses += ["Possible water stress", "Possible nutrient stress"]
    if _has_any(combined, _DRYING_KEYS):
        hypotheses += ["Premature drying; multiple causes possible"]
    if _has_any(combined, _SPOT_KEYS):
        hypotheses += ["Rust-like symptoms", "Possible leaf spots or disease"]
    if _has_any(combined, _INSECT_KEYS):
        hypotheses += ["Possible insect damage"]
    hypotheses = list(dict.fromkeys(hypotheses))

    cause_unknown = not has_evidence or not hypotheses
    if not has_evidence:
        possible_causes = ["Cause cannot be assessed from the information provided"]
    elif not hypotheses:
        possible_causes = ["No cause is distinguished by the available evidence"]
    else:
        possible_causes = hypotheses

    # ------------------------------------------------------------------
    # Farmer-answerable, non-chemical field checks (rule_based_check).
    # ------------------------------------------------------------------
    checks: list[str] = []
    if _has_any(combined, ("yellow", "wilt", "roll", "dry")):
        checks.append(
            "Compare older and younger leaves and note whether the change starts "
            "on the old or the new leaves."
        )
        checks.append(
            "Check whether the pattern is uniform across the field or patchy, and "
            "press the root-zone soil by hand in an affected spot and in a "
            "healthy-looking spot."
        )
    if _has_any(combined, _SPOT_KEYS):
        checks.append(
            "Inspect both sides of several affected leaves: note the colour of any "
            "spots or pustules, where they sit on the leaf, and whether healthy-looking "
            "plants nearby are unaffected."
        )
    if _has_any(combined, ("wilt", "roll")):
        checks.append(
            "Note whether leaves are rolling or plants are wilting, and whether they "
            "recover overnight."
        )
    if _has_any(combined, _INSECT_KEYS):
        checks.append(
            "Look under leaves and around the plant base, and record whether insects "
            "are visible on several plants."
        )
    if _has_any(combined, ("yellow", "wilt", "roll", "dry")):
        checks.append(
            "Ask whether the field was irrigated or received rain recently, and whether "
            "symptoms changed afterwards."
        )
    if _text(intake.get("symptoms_spreading")).strip().lower() == "yes":
        checks.append(
            "Mark the edge of the affected patch and record whether symptoms are "
            "spreading from the edge inward or in scattered spots across the field."
        )
    if not checks:
        checks.append(
            "Inspect several plants across the field and compare affected parts with "
            "healthy-looking parts."
        )
    checks = list(dict.fromkeys(checks))[:5]
    content_checks = list(checks)

    # ------------------------------------------------------------------
    # Expert-review referral triggers (C5). Reasons are recorded for audit.
    # ------------------------------------------------------------------
    notes = _text(intake.get("notes"))
    symptom_text = " ".join(raw_symptoms)
    asks_chemicals = bool(_CHEMICAL_QUESTION.search(notes) or _CHEMICAL_QUESTION.search(symptom_text))
    moisture = _text(intake.get("soil_moisture")).strip().lower()
    drainage = _text(intake.get("drainage")).strip().lower()
    stage = _text(intake.get("growth_stage")).strip().lower().replace("-", "_")
    spreading = _text(intake.get("symptoms_spreading")).strip().lower() == "yes"
    rust_evidence = _has_any(combined, ("rust", "pustule"))
    conflicting = (
        (moisture == "wet" or drainage in {"poor", "waterlogging"})
        and _has_any(combined, ("dry", "wilt", "roll"))
    )

    reasons: list[str] = []
    if rust_evidence:
        reasons.append("rust_like_pustules_reported_or_observed")
    if spreading:
        reasons.append("symptoms_rapidly_spreading")
    if stage in _HEADING_TO_GRAIN_STAGES and has_evidence:
        reasons.append("heading_to_grain_stage_with_symptoms")
    if cause_unknown:
        reasons.append("cause_remains_unknown")
    if band == "low":
        reasons.append("evidence_low")
    if conflicting:
        reasons.append("evidence_conflicting")
    if asks_chemicals:
        reasons.append("farmer_asked_about_chemicals")
    reasons = list(dict.fromkeys(reasons))
    referral = bool(reasons)
    if referral:
        checks.append(_REFERRAL_NOTE)

    # ------------------------------------------------------------------
    # Status, evidence separation and provenance.
    # ------------------------------------------------------------------
    if not has_evidence:
        status = "partial"
        evidence_reason = (
            "Evidence is insufficient: no usable farmer-reported or photo-visible "
            "symptom evidence, so only safe general inspection checks are provided. "
            + _UNVERIFIED_REASON
            + " Evidence quality only, not a probability or diagnosis."
        )
        checks = [
            "Describe which plant part looks different and whether the pattern is uniform or patchy.",
            "Compare several affected plants with a healthy-looking area.",
        ] + ([_REFERRAL_NOTE] if referral else [])
        content_checks = checks[:-1] if referral else list(checks)
    else:
        status = "complete"
        evidence_reason = (
            "Evidence quality only, not a probability or diagnosis: farmer-reported and "
            "photo-visible observations are labelled separately and are not locally verified. "
            + _UNVERIFIED_REASON
        )

    observations = list(farmer_evidence) + [f"Photo visible: {item}" for item in photo_evidence]
    input_evidence = [f"farmer_reported: {label}" for label in farmer_evidence]
    if photo_evidence:
        input_evidence += [f"photo_visible: {item}" for item in photo_evidence]
    else:
        input_evidence.append(
            "photo_visible: none (vision unavailable, not assessed, or returned no observations)"
        )
    input_evidence.append(
        "rule_based_check: deterministic crop screening rules (provisional, unverified; "
        f"registry id: {SOURCE_REGISTRY_ID})"
    )

    data = {
        "referral_recommended": referral,
        "referral_reasons": reasons,
        "supported_crop": "wheat",
        "vision_used": bool(photo_evidence),
        "vision_status": vision_status,
        "evidence_labels": {
            "farmer_reported": list(farmer_evidence),
            "photo_visible": list(photo_evidence),
            "rule_based_check": list(content_checks),
        },
        "rule_verification": {
            "status": "unverified",
            "source_registry_id": SOURCE_REGISTRY_ID,
            "note": _UNVERIFIED_REASON,
        },
    }

    return AgentResult(
        assessment_id=assessment_id,
        agent_id="crop",
        status=status,
        summary=(
            "There is not enough symptom evidence to distinguish possible causes."
            if not has_evidence
            else "The findings below are screening possibilities only; similar visible "
            "changes can have different causes."
        ),
        observations=observations,
        possible_causes=possible_causes,
        checks=checks,
        evidence_band=band,
        evidence_reason=evidence_reason,
        sources=[],
        provider_or_model="deterministic-wheat-screening-rules",
        version=VERSION,
        created_at=datetime.now(UTC),
        safety_flags=[
            "not_a_diagnosis",
            "local_validation_pending",
            "crop_rules_unverified",
            "no_chemical_guidance",
        ],
        data=data,
        input_evidence=input_evidence,
    )

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas import AgentResult

VERSION = "crop-rules-1.0.0"

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


def assess_crop(assessment_id: str, intake: dict[str, Any], vision: AgentResult | None) -> AgentResult:
    reported_tags = [t for t in intake.get("symptoms", []) if t in SYMPTOM_LABELS]
    farmer_evidence = [SYMPTOM_LABELS[t] for t in reported_tags]
    photo_evidence = list(vision.observations) if vision and vision.status in {"complete", "partial"} else []
    combined = " ".join(farmer_evidence + photo_evidence).lower()

    possible: list[str] = []
    checks: list[str] = []
    referral = intake.get("symptoms_spreading") == "yes"
    if any(k in combined for k in ("yellow", "drying", "wilting", "rolling")):
        possible.extend(
            [
                "Possible water stress",
                "Possible nutrient-related stress",
                "Other environmental or crop conditions may overlap",
            ]
        )
        checks.append(
            "Compare older and younger leaves and note whether changes are uniform or patchy across several plants."
        )
        checks.append(
            "Check root-zone soil moisture by hand and compare an affected patch with a healthy-looking patch."
        )
    if any(k in combined for k in ("spot", "pustule", "rust-like", "rust like")):
        possible.extend(
            [
                "Rust-like symptoms or other leaf spotting are possibilities; an image cannot confirm the cause",
                "Physical damage or environmental stress may look similar",
            ]
        )
        checks.append(
            "Inspect both sides of several affected leaves and compare the markings with healthy plants nearby."
        )
        referral = True
    if any(k in combined for k in ("insect", "aphid", "hole")):
        possible.append("Possible insect feeding; the insect type and significance have not been established")
        checks.append(
            "Look under leaves and around the plant base; record whether insects are present on multiple plants."
        )
    if intake.get("symptoms_spreading") == "yes":
        checks.append(
            "Mark the edge of the affected patch and ask a local agriculture extension expert to review spreading symptoms."
        )
    if not farmer_evidence and not photo_evidence:
        status, band = "partial", "low"
        summary = "There is not enough symptom evidence to distinguish possible causes."
        possible = ["Cause cannot be assessed from the information provided"]
        checks = [
            "Describe which plant part looks different and whether the pattern is uniform or patchy.",
            "Compare several affected plants with a healthy-looking area.",
        ]
    else:
        status = "complete"
        band = "medium" if farmer_evidence and photo_evidence else "low"
        summary = (
            "The findings below are screening possibilities only; similar visible changes can have different causes."
        )
        if not possible:
            possible = ["No cause is distinguished by the available evidence"]
        if not checks:
            checks = ["Inspect several plants and compare affected and healthy-looking areas."]
    if referral:
        checks.append(
            "For spreading, rust-like, severe, or unclear signs, seek review from a local agriculture officer or qualified expert."
        )
    checks = list(dict.fromkeys(checks))[:5]
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="crop",
        status=status,
        summary=summary,
        observations=farmer_evidence + [f"Photo visible: {item}" for item in photo_evidence],
        possible_causes=list(dict.fromkeys(possible)),
        checks=checks,
        evidence_band=band,
        evidence_reason="Evidence quality only, not a probability or diagnosis. Farmer reports and image-visible observations are labelled separately; local symptom validation is pending.",
        sources=[],
        provider_or_model="deterministic-wheat-screening-rules",
        version=VERSION,
        created_at=datetime.now(UTC),
        safety_flags=["not_a_diagnosis", "local_validation_pending"],
        data={"referral_recommended": referral, "supported_crop": "wheat"},
        input_evidence=farmer_evidence
        + (
            ["Vision observation(s) available"]
            if photo_evidence
            else ["Vision observation unavailable or not assessed"]
        ),
    )

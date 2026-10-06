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

The result also carries a structured evidence split in ``data`` so the UI can
show the two evidence classes, the screening possibilities, the field checks
and the escalation signs under separate headings:
  farmer_reported_symptoms, photo_visible_findings, crop_possibilities,
  field_checks (max 3), escalation_signs.

Checks are symptom-aware and deterministic: rust-like evidence (reported or
photo-visible), yellowing, premature drying, wilting, spots, insects, the
spreading flag, a healthy-looking photo that contradicts farmer-reported
symptoms, and an unclear photo each select a small, non-duplicated set of at
most three high-value checks. Vocabulary stays cautious throughout: "possible",
"visible sign", "needs verification" - never diagnosis, treatment, or a
confirmed cause.

Expert-review referral triggers (recorded in data["referral_reasons"]):
- rust-like pustules reported or observed
- symptoms rapidly spreading
- heading-to-grain growth stage with symptom evidence
- cause remains unknown
- evidence is low or conflicting
- farmer asks about a chemical/treatment

Only the first four kinds of reason ever produce ``escalation_signs``; missing
or low information alone never recommends an expert review.

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
    "rust-like, severe, or unclear symptoms before any action."
)

_UNVERIFIED_REASON = (
    "Crop screening rules are provisional and unverified: the source registry "
    f"holds no externally verified Crop agronomy source record (registry id: {SOURCE_REGISTRY_ID})."
)

# ------------------------------------------------------------------ vision
# The Vision gateway's app-safe visible classes. Crop only ever consumes
# these three plus an explicit "absent" state; any other observation text is
# kept as photo evidence but does not select a rule on its own.
SAFE_VISIBLE_CLASSES = {"healthy_looking", "rust_like_pustules", "unclear"}

_FINDING_PREFIXES = (
    ("no clear visible symptoms", "healthy_looking"),
    ("rust-like marks visible", "rust_like_pustules"),
    ("image details unclear", "unclear"),
)

# ------------------------------------------------------- screening language
# Cautious vocabulary only: a possibility, never a confirmed cause.
_POSSIBILITY_RUST = (
    "Rust-like leaf signs need field verification; the cause is not confirmed."
)

# -------------------------------------------------- farmer-answerable checks
# Fixed wording (i18n maps these exact strings). Each one is an observation
# task: no product, dose, spray schedule, irrigation amount or timing.
_CHECK_LEAF_AGE = (
    "Compare older and younger leaves and note whether the change starts "
    "on the old or the new leaves."
)
_CHECK_UNIFORM = "Check whether the pattern is uniform across the field or patchy."
_CHECK_ROOT_ZONE = (
    "Check root-zone soil moisture, drainage, and roots before attributing a cause."
)
_CHECK_COMPARE_DRY = (
    "Compare dry plants with healthy-looking plants at several locations."
)
_CHECK_DRY_ORIGIN = (
    "Record whether the drying starts from leaf tips, leaf margins, or whole leaves."
)
_CHECK_WILT_RECOVERY = (
    "Note whether leaves are rolling or plants are wilting, and whether they "
    "recover overnight."
)
_CHECK_PATCHES = "Compare affected and unaffected patches at several locations."
_CHECK_SPOTS = (
    "Inspect both sides of several affected leaves: note the shape and colour "
    "of any spots, where they sit on the leaf, and whether both leaf surfaces "
    "are affected."
)
_CHECK_INSECTS = (
    "Look under leaves and around the plant base, and record whether insects "
    "are visible on several plants."
)
_CHECK_SPREADING = (
    "Mark the edge of the affected patch and record whether symptoms are "
    "spreading from the edge inward or in scattered spots across the field."
)
_CHECK_GENERIC = (
    "Inspect several plants across the field and compare affected parts with "
    "healthy-looking parts."
)
_CHECK_DESCRIBE = (
    "Describe which plant part looks different and whether the pattern is "
    "uniform or patchy."
)
_CHECK_COMPARE_HEALTHY = (
    "Compare several affected plants with a healthy-looking area."
)

# Rule A: rust-like evidence reported by the farmer or visible in the photo.
_CHECKS_RUST = (
    "Inspect both sides of 5–10 affected leaves and record whether raised "
    "orange, yellow, or brown marks are present.",
    "Compare affected plants with nearby healthy-looking plants and note "
    "whether marks are scattered or arranged in lines.",
    "Check whether newer leaves are becoming affected.",
)

# Rules G and H: photo vs. farmer statements (kept as statements, never as a
# cause claim).
_STATEMENT_DISCREPANCY = (
    "The uploaded photo did not show clear visible signs, while the farmer "
    "reported symptoms. Check multiple affected plants; the photo does not "
    "rule out a field problem."
)
_STATEMENT_PHOTO_LIMIT = (
    "The uploaded photo did not show readable details, so no visible sign was "
    "read from it; this limits the photo evidence only and says nothing about "
    "the field."
)
# Vision identified the subject as a wheat ear/head and said leaf screening
# does not apply: the photo is readable, it simply is not a leaf close-up, so
# the "unreadable photo" limitation above must never be shown for it.
_PHOTO_EAR_STATEMENT = (
    "A wheat ear/head is visible in the photo. The image does not show leaf "
    "symptoms for screening."
)

# --------------------------------------------- expert-review escalation signs
_ESCALATION_RUST = (
    "Seek local expert review if marks spread quickly, appear on new leaves, "
    "or affect a larger part of the field."
)
_ESCALATION_SPREADING = (
    "Seek local expert review if the affected area keeps spreading quickly or "
    "new plants become affected."
)
_ESCALATION_CONFLICT = (
    "Ask a local agriculture officer to review signs that do not fit together "
    "before any action."
)
_ESCALATION_STAGE = (
    "Ask a local agriculture officer to review symptoms seen at the "
    "heading-to-grain stages."
)
_ESCALATION_CHEMICAL = (
    "Ask a local agriculture officer to answer any product or input question "
    "before acting."
)
_ESCALATION_UNCLEAR = (
    "Ask a local agriculture officer to review unclear or severe-looking signs "
    "before any action."
)

_ESCALATION_BY_REASON = {
    "rust_like_pustules_reported_or_observed": _ESCALATION_RUST,
    "symptoms_rapidly_spreading": _ESCALATION_SPREADING,
    "evidence_conflicting": _ESCALATION_CONFLICT,
    "heading_to_grain_stage_with_symptoms": _ESCALATION_STAGE,
    "farmer_asked_about_chemicals": _ESCALATION_CHEMICAL,
    "unsupported_crop_scope": _ESCALATION_UNCLEAR,
}

# Reasons that only mean information is missing or thin. They stay on the card
# for audit but never recommend an expert review on their own.
_INFORMATION_ONLY_REASONS = {"cause_remains_unknown", "evidence_low"}


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


def _vision_finding(vision: Any, status: str, photo: list[str]) -> str:
    """App-safe visible class for the photo: healthy | rust-like | unclear.

    The gateway's own ``mapped_visible_finding`` is preferred when present;
    otherwise the fixed observation prefixes are matched. Returns "absent"
    when Vision contributed nothing, "other" for any other visible finding.
    """
    if status not in {"complete", "partial"} or not photo:
        return "absent"

    if isinstance(vision, dict):
        data = vision.get("data") or {}
    else:
        data = getattr(vision, "data", None) or {}

    diagnostics = data.get("diagnostics") if isinstance(data, dict) else None
    mapped = (
        diagnostics.get("mapped_visible_finding")
        if isinstance(diagnostics, dict)
        else None
    )
    if mapped in SAFE_VISIBLE_CLASSES:
        return mapped

    lowered = " ".join(photo).lower()
    for prefix, visible_class in _FINDING_PREFIXES:
        if prefix in lowered:
            return visible_class

    return "other"


def _vision_scope(vision: Any) -> tuple[str, str, str]:
    """(photo_subject, screening_scope, photo_quality) as Vision reported them.

    Crop never re-derives the plant part: it only reads the gateway's own
    screening-scope fields so it can describe the photo evidence the same way
    Vision did. Missing/legacy data yields empty strings, which keeps the
    existing unclear-photo behaviour untouched.
    """
    if isinstance(vision, dict):
        data = vision.get("data") or {}
    else:
        data = getattr(vision, "data", None) or {}
    if not isinstance(data, dict):
        return "", "", ""
    report = data.get("photo_report")
    report = report if isinstance(report, dict) else {}
    photo_subject = _text(data.get("photo_subject") or report.get("photo_subject")).strip()
    screening_scope = _text(
        data.get("screening_scope") or report.get("screening_scope")
    ).strip()
    photo_quality = _text(report.get("photo_quality")).strip()
    return photo_subject, screening_scope, photo_quality


def _unsupported(assessment_id: str, crop_name: str) -> AgentResult:
    """Wheat-only scope guard: abstain instead of screening other crops."""
    check = "Select wheat, or ask a local agriculture expert about this crop."

    return AgentResult(
        assessment_id=assessment_id,
        agent_id="crop",
        status="unsupported",
        summary="The Crop Agent supports wheat only; no crop assessment was made for this crop.",
        observations=[],
        possible_causes=[],
        checks=[
            check,
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
            "vision_finding": "absent",
            "evidence_labels": {
                "farmer_reported": [],
                "photo_visible": [],
                "rule_based_check": [],
            },
            "farmer_reported_symptoms": [],
            "photo_visible_findings": [],
            "crop_possibilities": [],
            "field_checks": [check],
            "escalation_signs": [_REFERRAL_NOTE],
            "rule_verification": {
                "status": "unverified",
                "source_registry_id": SOURCE_REGISTRY_ID,
                "note": _UNVERIFIED_REASON,
            },
        },
        input_evidence=[f"crop_scope: reported crop '{crop_name}' is outside the supported wheat scope"],
    )


def _symptom_field_checks(
    combined: str,
    *,
    rust_rule: bool,
    spreading: bool,
    photo_discrepancy: bool,
) -> list[str]:
    """Deterministic, symptom-aware field checks (max 3, no duplicates).

    Rust-like evidence owns all three slots because it carries the escalation
    path. Otherwise each situation contributes at most one round of checks:
    when more than one symptom is active the first check of each symptom is
    kept first so no symptom disappears from the plan, then the shared
    root-zone check, then any deeper per-symptom checks.
    """
    if rust_rule:
        return list(_CHECKS_RUST)

    yellow = _has_any(combined, ("yellow",))
    drying = _has_any(combined, _DRYING_KEYS)
    wilting = _has_any(combined, ("wilt", "roll"))
    spots = _has_any(combined, _SPOT_KEYS)
    insects = _has_any(combined, _INSECT_KEYS)

    groups: list[list[str]] = []

    if spreading:
        groups.append([_CHECK_SPREADING])

    if photo_discrepancy:
        groups.append([_STATEMENT_DISCREPANCY])

    if yellow:
        groups.append([_CHECK_LEAF_AGE, _CHECK_UNIFORM])

    if drying:
        groups.append([_CHECK_COMPARE_DRY, _CHECK_DRY_ORIGIN])

    if wilting:
        groups.append([_CHECK_WILT_RECOVERY, _CHECK_PATCHES])

    if spots:
        groups.append([_CHECK_SPOTS])

    if insects:
        groups.append([_CHECK_INSECTS])

    if not groups:
        return [_CHECK_GENERIC, _CHECK_DESCRIBE]

    needs_root_zone = yellow or drying or wilting

    if len(groups) == 1:
        picks = list(groups[0][:2])
        if needs_root_zone:
            picks.append(_CHECK_ROOT_ZONE)
        picks.extend(groups[0][2:3])
    else:
        picks = [group[0] for group in groups]
        if needs_root_zone:
            picks.append(_CHECK_ROOT_ZONE)
        picks.extend(item for group in groups for item in group[1:])

    picks = list(dict.fromkeys(picks))[:3]

    if len(picks) < 2:
        for filler in (_CHECK_GENERIC, _CHECK_DESCRIBE):
            if filler not in picks:
                picks.append(filler)
            if len(picks) >= 2:
                break

    return picks[:3]


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

    finding = _vision_finding(vision, vision_status, photo_evidence)

    # Plant part / screening scope exactly as Vision reported it. Crop never
    # re-derives the subject; it only avoids contradicting the Vision card.
    photo_subject, screening_scope, photo_quality = _vision_scope(vision)
    ear_head_photo = bool(photo_evidence) and (
        photo_subject == "wheat_ear_or_head"
        and screening_scope == "leaf_screening_not_applicable"
    )
    # A photo whose subject Vision identified clearly is not an "unclear
    # sign": the frame was readable, it simply was not a leaf close-up.
    clear_non_leaf_photo = (
        screening_scope == "leaf_screening_not_applicable" and photo_quality == "clear"
    )

    # ------------------------------------------------------------------
    # Intake scalars used by the rules (never echoed back verbatim).
    # ------------------------------------------------------------------
    notes = _text(intake.get("notes"))
    symptom_text = " ".join(raw_symptoms)
    asks_chemicals = bool(_CHEMICAL_QUESTION.search(notes) or _CHEMICAL_QUESTION.search(symptom_text))
    moisture = _text(intake.get("soil_moisture")).strip().lower()
    drainage = _text(intake.get("drainage")).strip().lower()
    stage = _text(intake.get("growth_stage")).strip().lower().replace("-", "_")
    spreading = _text(intake.get("symptoms_spreading")).strip().lower() == "yes"

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

    rust_rule = finding == "rust_like_pustules" or "rust" in combined or "pustule" in combined
    photo_discrepancy = bool(
        has_evidence and finding == "healthy_looking" and farmer_evidence
    )

    if rust_rule:
        hypotheses = [h for h in hypotheses if h != "Rust-like symptoms"]
        hypotheses.insert(0, _POSSIBILITY_RUST)

    cause_unknown = not has_evidence or not hypotheses
    if not has_evidence:
        possible_causes = ["Cause cannot be assessed from the information provided"]
    elif not hypotheses:
        possible_causes = ["No cause is distinguished by the available evidence"]
    else:
        possible_causes = hypotheses

    # ------------------------------------------------------------------
    # Deterministic, symptom-aware field checks (max 3) + escalation note.
    # ------------------------------------------------------------------
    content_checks = _symptom_field_checks(
        combined,
        rust_rule=rust_rule,
        spreading=spreading,
        photo_discrepancy=photo_discrepancy,
    )

    # ------------------------------------------------------------------
    # Expert-review referral triggers (C5). Reasons are recorded for audit.
    # ------------------------------------------------------------------
    conflicting = (
        (moisture == "wet" or drainage in {"poor", "waterlogging"})
        and _has_any(combined, ("dry", "wilt", "roll"))
    )

    reasons: list[str] = []
    if rust_rule:
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

    # Escalation signs: only real escalation criteria, never "information is
    # missing". An unclear photo with reported symptoms also counts. When a
    # referral exists without a specific criterion, the standing referral
    # note keeps the "how to escalate" instruction visible.
    escalation_signs: list[str] = []
    if finding == "unclear" and has_evidence and not clear_non_leaf_photo:
        escalation_signs.append(_ESCALATION_UNCLEAR)
    for reason in reasons:
        if reason in _INFORMATION_ONLY_REASONS:
            continue
        sign = _ESCALATION_BY_REASON.get(reason)
        if sign and sign not in escalation_signs:
            escalation_signs.append(sign)

    if referral and not escalation_signs:
        escalation_signs.append(_REFERRAL_NOTE)

    checks = list(content_checks)
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
            _CHECK_DESCRIBE,
            _CHECK_COMPARE_HEALTHY,
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

    # Rules G and H are carried by the structured evidence split so they stay
    # separate from any cause claim: the healthy-photo/farmer discrepancy is a
    # field check, the unclear-photo limitation is reported with the photo
    # evidence it limits. Neither is ever phrased as a diagnosis. An ear/head
    # photo is readable evidence of a non-leaf subject, so it gets the scope
    # statement instead of any "unreadable photo" wording.
    photo_visible_findings = list(photo_evidence)
    if ear_head_photo:
        photo_visible_findings = [_PHOTO_EAR_STATEMENT]
    elif has_evidence and finding == "unclear" and farmer_evidence:
        photo_visible_findings.append(_STATEMENT_PHOTO_LIMIT)

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
        "vision_finding": finding,
        "evidence_labels": {
            "farmer_reported": list(farmer_evidence),
            "photo_visible": list(photo_evidence),
            "rule_based_check": list(content_checks),
        },
        # Structured evidence split consumed by the result UI.
        "farmer_reported_symptoms": list(farmer_evidence),
        "photo_visible_findings": photo_visible_findings,
        "crop_possibilities": list(possible_causes),
        "field_checks": list(content_checks),
        "escalation_signs": list(escalation_signs),
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

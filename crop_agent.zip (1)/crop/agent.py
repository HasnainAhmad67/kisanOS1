"""
KisanOS — Crop Agent (Wheat)
Module: agents/crop/agent.py
Member 4 Implementation

Analyzes wheat crop stress indicators based on:
- Growth stage (from sowing date or explicit input)
- Farmer-reported symptoms (yellowing, wilting, stunting, etc.)
- Days since last irrigation
- Local agro-climatic context (Bahawalpur pilot)

Returns strict Canonical JSON matching the KisanOS Multi-Agent Contract.
Strictly non-chemical: returns observations, possible causes, and field checks only.
"""

import os
import sys
import uuid
import json
import logging
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional, List, Tuple

try:
    from .schema import (
        CropAgentResponse, SourceRecord, CropDetails,
        validate_crop_payload, _validate_uuid,
        VALID_GROWTH_STAGES,
    )
    from .ai_enhance import enhance_with_gemini, get_deterministic_urdu_enhancement
except ImportError:
    from schema import (
        CropAgentResponse, SourceRecord, CropDetails,
        validate_crop_payload, _validate_uuid,
        VALID_GROWTH_STAGES,
    )
    from ai_enhance import enhance_with_gemini, get_deterministic_urdu_enhancement

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("kisanos.agents.crop")


# ═══════════════════════════════════════════════════════════════
# WHEAT GROWTH STAGES (Days after sowing, Punjab Rabi season)
# Source: PARC Wheat Production Guide + Punjab Agriculture Dept
# ═══════════════════════════════════════════════════════════════
WHEAT_GROWTH_STAGES = [
    {"stage": "germination", "min_day": 0,   "max_day": 15,  "next_in_days": 15},
    {"stage": "tillering",   "min_day": 15,  "max_day": 60,  "next_in_days": 45},
    {"stage": "booting",     "min_day": 60,  "max_day": 80,  "next_in_days": 20},
    {"stage": "heading",     "min_day": 80,  "max_day": 95,  "next_in_days": 15},
    {"stage": "flowering",   "min_day": 95,  "max_day": 105, "next_in_days": 10},
    {"stage": "grain_fill",  "min_day": 105, "max_day": 130, "next_in_days": 25},
    {"stage": "maturity",    "min_day": 130, "max_day": 150, "next_in_days": 20},
]


# ═══════════════════════════════════════════════════════════════
# WHEAT STRESS INDICATOR KNOWLEDGE BASE
# Each entry: symptom keyword → possible causes + non-chemical checks
# Sources: PARC, Punjab Agriculture Dept, FAO Wheat Guide
# ═══════════════════════════════════════════════════════════════
WHEAT_STRESS_KNOWLEDGE_BASE = {
    "yellowing_lower_leaves": {
        "aliases": [
            "yellowing leaves", "lower leaves yellow", "pale leaves",
            "purani patti peeli", "pattay peele", "yellow leaves"
        ],
        "stages_relevant": ["tillering", "booting", "heading"],
        "possible_causes": [
            "Nitrogen deficiency (mobile nutrient moves to new growth, older leaves yellow first)",
            "Waterlogged root zone reducing nitrogen uptake",
            "Prolonged cold stress during early tillering",
        ],
        "checks": [
            "Inspect the pattern: uniform yellowing from leaf tip inward suggests nitrogen movement to new growth.",
            "Check soil moisture at 10 cm depth — waterlogged soil can mimic nitrogen deficiency.",
            "Examine root color: healthy roots are white/cream; brown roots indicate root-zone stress.",
            "Compare border rows vs center rows — border effect suggests nutrient or moisture gradient.",
        ],
        "severity_hint": "moderate",
    },
    "yellowing_upper_leaves": {
        "aliases": [
            "top leaves yellow", "new leaves pale", "upper leaf yellowing",
            "naye pattay peele"
        ],
        "stages_relevant": ["tillering", "booting", "heading", "flowering"],
        "possible_causes": [
            "Sulfur deficiency (immobile nutrient — new growth affected first)",
            "Cold shock during early vegetative stage",
            "Zinc deficiency in alkaline soils (common in southern Punjab)",
        ],
        "checks": [
            "Inspect youngest leaves specifically — sulfur deficiency shows on newest growth.",
            "Check field history: has this field shown similar symptoms in previous seasons?",
            "Examine leaf shape — narrow, small leaves suggest zinc deficiency in wheat.",
            "Note any interveinal yellowing pattern (veins stay green).",
        ],
        "severity_hint": "moderate",
    },
    "wilting": {
        "aliases": [
            "wilting", "drooping", "wilted leaves", "murjha rahe hain",
            "leaves drooping", "plant wilting"
        ],
        "stages_relevant": ["tillering", "booting", "heading", "flowering", "grain_fill"],
        "possible_causes": [
            "Water stress — soil moisture depleted in root zone",
            "Root damage from waterlogging or soil compaction",
            "High daytime temperature causing transpiration exceeding water uptake",
        ],
        "checks": [
            "Time the wilting: wilting in afternoon that recovers by evening suggests mild water stress.",
            "Wilting that persists overnight indicates serious water or root stress.",
            "Check soil moisture at 10 cm and 20 cm depths — dry at both = irrigation likely needed.",
            "Inspect root zone by carefully digging a 15 cm pit at field edge.",
        ],
        "severity_hint": "high",
    },
    "stunted_growth": {
        "aliases": [
            "stunted", "small plants", "short plants", "kamzor poday",
            "poor growth", "slow growth"
        ],
        "stages_relevant": ["tillering", "booting", "heading"],
        "possible_causes": [
            "Phosphorus deficiency (common in early growth)",
            "Soil compaction restricting root development",
            "Poor seedbed preparation or late sowing",
            "Water stress during critical growth window",
        ],
        "checks": [
            "Compare plant height across field — patchy stunting suggests localized soil issue.",
            "Inspect root system: shallow, poorly-branched roots suggest compaction or phosphorus issue.",
            "Check sowing date — late-sown wheat often shows stunted early growth.",
            "Compare with neighboring fields sown at similar time for a baseline.",
        ],
        "severity_hint": "moderate",
    },
    "brown_orange_spots": {
        "aliases": [
            "brown spots", "orange spots", "rust", "zang", "brown patches",
            "yellow-brown spots", "leaf spots"
        ],
        "stages_relevant": ["tillering", "booting", "heading", "flowering"],
        "possible_causes": [
            "Stripe rust (Puccinia striiformis) favored by 15-22°C + high humidity",
            "Leaf rust (Puccinia triticina) favored by 15-25°C + dew",
            "Nutrient imbalance making plants susceptible to foliar pathogens",
        ],
        "checks": [
            "Inspect leaf underside in early morning for powdery orange-yellow spores.",
            "Note the pattern: stripes = stripe rust; scattered spots = leaf rust.",
            "Check lower canopy first — rust typically starts low and moves up.",
            "Photograph and consult local agriculture extension officer if spreading fast.",
        ],
        "severity_hint": "high",
    },
    "white_powdery_patches": {
        "aliases": [
            "white powder", "powdery patches", "white spots", "safed powder",
            "white coating on leaves"
        ],
        "stages_relevant": ["tillering", "booting", "heading"],
        "possible_causes": [
            "Powdery mildew (Blumeria graminis) favored by cool humid conditions",
            "Poor canopy airflow due to dense sowing",
        ],
        "checks": [
            "Inspect upper leaf surface for white powdery patches that wipe off.",
            "Check canopy density — dense sowing traps humidity favoring mildew.",
            "Examine spread pattern — powdery mildew spreads fast in humid conditions.",
            "Note if patches are localized or field-wide.",
        ],
        "severity_hint": "moderate",
    },
    "chewed_leaf_edges": {
        "aliases": [
            "chewed leaves", "eaten leaves", "holes in leaves", "insects",
            "keeray", "leaf damage", "pest damage"
        ],
        "stages_relevant": ["germination", "tillering", "booting"],
        "possible_causes": [
            "Insect pest feeding (armyworm, aphids, or termites in early stage)",
            "Slug or snail damage in damp patches",
        ],
        "checks": [
            "Scout at dawn or dusk — most pest activity occurs in early/late hours.",
            "Inspect leaf undersides and plant base for insects or larvae.",
            "Look for clusters — most pests are found in patches initially.",
            "Check soil surface at plant base for cut stems (cutworm damage).",
        ],
        "severity_hint": "moderate",
    },
    "empty_dry_spikes": {
        "aliases": [
            "empty spikes", "dry spikes", "no grain", "khali bali",
            "spike drying", "white spikes"
        ],
        "stages_relevant": ["heading", "flowering", "grain_fill"],
        "possible_causes": [
            "Heat stress during flowering (>32°C causes pollen sterility)",
            "Frost damage during heading (below 4°C)",
            "Water stress during grain filling",
        ],
        "checks": [
            "Review temperature history for last 10-15 days for heat/frost events.",
            "Inspect spikelets — partial emptiness suggests partial stress event.",
            "Check whether neighboring fields show the same pattern (regional event vs. field-specific).",
            "Consult local extension officer for grain-fill management guidance.",
        ],
        "severity_hint": "high",
    },
}


# ═══════════════════════════════════════════════════════════════
# SYMPTOM NORMALIZER — map farmer input to KB keys
# ═══════════════════════════════════════════════════════════════
def normalize_symptoms(raw_symptoms: List[str]) -> List[str]:
    """Maps free-text farmer symptoms to canonical KB keys."""
    matched: List[str] = []
    for raw in raw_symptoms or []:
        if not raw:
            continue
        lowered = str(raw).strip().lower()
        # Direct match
        if lowered in WHEAT_STRESS_KNOWLEDGE_BASE:
            if lowered not in matched:
                matched.append(lowered)
            continue
        # Alias match
        found = False
        for key, entry in WHEAT_STRESS_KNOWLEDGE_BASE.items():
            for alias in entry.get("aliases", []):
                if alias in lowered or lowered in alias:
                    if key not in matched:
                        matched.append(key)
                    found = True
                    break
            if found:
                break
    return matched


def stage_from_sowing_date(sowing_date_str: Optional[str]) -> Tuple[str, Optional[int], Optional[int]]:
    """
    Returns (stage, days_since_sowing, next_stage_expected_days).
    Defaults to 'unknown' if date missing/unparseable.
    """
    if not sowing_date_str:
        return "unknown", None, None
    try:
        sow = date.fromisoformat(sowing_date_str.strip())
    except Exception:
        return "unknown", None, None

    days = (date.today() - sow).days
    if days < 0:
        return "unknown", days, None

    for entry in WHEAT_GROWTH_STAGES:
        if entry["min_day"] <= days < entry["max_day"]:
            return entry["stage"], days, entry["next_in_days"]
    return "maturity", days, None


class CropAgent:
    """KisanOS Crop Agent — wheat-specific stress analysis engine."""

    def __init__(self, crop_type: str = "wheat"):
        self.crop_type = crop_type
        self.version = "1.0"

    def analyze(
        self,
        assessment_id: Optional[str] = None,
        crop: str = "wheat",
        growth_stage: Optional[str] = None,
        sowing_date: Optional[str] = None,
        days_since_irrigation: Optional[int] = None,
        symptoms: Optional[List[str]] = None,
        tehsil_or_coords: Optional[str] = None,
        enable_ai: bool = True,
        force_offline: bool = False,
    ) -> CropAgentResponse:
        """Main analysis pipeline. Returns strict canonical JSON."""

        # ─── 1. Validate / generate UUID ───
        if assessment_id is not None:
            ass_id = _validate_uuid(assessment_id)
        else:
            ass_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # ─── 2. Resolve crop type ───
        crop_type = (crop or "wheat").strip().lower()
        safety_flags: List[str] = []
        if crop_type != "wheat":
            safety_flags.append(
                f"UNSUPPORTED_CROP: '{crop_type}' is not yet supported in MVP. Only 'wheat' is calibrated. "
                f"Analysis degraded; please refer to local agriculture extension officer."
            )

        # ─── 3. Resolve growth stage ───
        resolved_stage = (growth_stage or "").strip().lower()
        days_since_sowing: Optional[int] = None
        next_stage_in_days: Optional[int] = None

        if resolved_stage in VALID_GROWTH_STAGES and resolved_stage != "unknown":
            pass  # explicit stage provided by farmer
        else:
            # auto-detect from sowing date
            stage_auto, days_auto, next_auto = stage_from_sowing_date(sowing_date)
            resolved_stage = stage_auto
            days_since_sowing = days_auto
            next_stage_in_days = next_auto

        # ─── 4. Normalize symptoms ───
        raw_symptoms = symptoms if isinstance(symptoms, list) else []
        matched_symptom_keys = normalize_symptoms(raw_symptoms)

        # ─── 5. Build observations / causes / checks ───
        observations: List[str] = []
        possible_causes: List[str] = []
        checks: List[str] = []
        stress_severity = "unknown"
        sev_rank = {"low": 1, "moderate": 2, "high": 3, "unknown": 0}
        max_sev = 0

        observations.append(f"Crop: {crop_type.capitalize()}. Growth stage: {resolved_stage}.")
        if days_since_sowing is not None:
            observations.append(f"Estimated {days_since_sowing} days since sowing (based on provided sowing date).")
        if days_since_irrigation is not None:
            observations.append(f"Last irrigation: {days_since_irrigation} days ago (farmer-reported).")

        # Generic soil moisture check always recommended
        base_checks = [
            "Check soil moisture manually at 10 cm depth by squeezing a handful of soil into a ball — crumbly = dry; holds shape = adequate; muddy = waterlogged.",
            "Walk diagonally across the field to spot any uneven pattern of stress (patchy vs uniform).",
        ]

        if not matched_symptom_keys:
            # No recognized symptoms — provide baseline guidance
            observations.append("No specific stress symptoms were recognized from farmer input.")
            possible_causes.append("Crop appears visually within normal range for the reported growth stage.")
            checks.extend(base_checks)
            evidence_band = "low"
            evidence_reason = "No specific symptoms provided or recognized; baseline agronomic guidance issued."
        else:
            # Merge KB info for each matched symptom
            for key in matched_symptom_keys:
                entry = WHEAT_STRESS_KNOWLEDGE_BASE[key]
                human = key.replace("_", " ")
                observations.append(f"Reported symptom: {human}.")
                for cause in entry["possible_causes"]:
                    if cause not in possible_causes:
                        possible_causes.append(cause)
                for chk in entry["checks"]:
                    if chk not in checks:
                        checks.append(chk)
                sev = entry.get("severity_hint", "moderate")
                if sev_rank.get(sev, 0) > max_sev:
                    max_sev = sev_rank[sev]
                    stress_severity = sev

            # Always append baseline checks at end
            for chk in base_checks:
                if chk not in checks:
                    checks.append(chk)

            # Days-since-irrigation-based additional guidance
            if isinstance(days_since_irrigation, int):
                if resolved_stage in ("tillering", "booting", "heading", "flowering", "grain_fill"):
                    if days_since_irrigation >= 12:
                        possible_causes.append(
                            f"Irrigation gap of {days_since_irrigation} days during {resolved_stage} stage may contribute to water stress."
                        )
                        checks.append(
                            f"Given {days_since_irrigation} days since last irrigation during {resolved_stage}, "
                            "verify soil moisture at 10 cm and 20 cm depth before deciding next irrigation."
                        )

            evidence_band = "medium" if max_sev >= 2 else "low"
            evidence_reason = (
                f"Based on {len(matched_symptom_keys)} farmer-reported symptom(s); field verification "
                f"by the farmer is required before any action."
            )

        # ─── 6. Stress severity final mapping ───
        if stress_severity == "unknown" and matched_symptom_keys:
            stress_severity = "moderate"

        # ─── 7. Build summary ───
        if matched_symptom_keys:
            symptom_human = ", ".join(k.replace("_", " ") for k in matched_symptom_keys)
            summary = (
                f"Wheat crop at {resolved_stage} stage shows {len(matched_symptom_keys)} reported stress indicator(s): "
                f"{symptom_human}. Severity assessed as {stress_severity}. "
                f"Non-chemical field verification recommended before any input decision."
            )
        else:
            summary = (
                f"Wheat crop at {resolved_stage} stage shows no specific recognizable stress indicators from "
                f"farmer input. Baseline agronomic monitoring recommended."
            )

        # ─── 8. Sources (always non-chemical advisory sources) ───
        sources: List[SourceRecord] = [
            SourceRecord(
                title="PARC Wheat Production & Protection Guide",
                url="http://www.parc.gov.pk/",
                publisher="Pakistan Agricultural Research Council (PARC)",
                retrieved_at=now_iso,
                source_status="official",
            ),
            SourceRecord(
                title="Punjab Agriculture Department — Wheat Advisory",
                url="https://www.agripunjab.gov.pk/",
                publisher="Agriculture Department, Government of Punjab",
                retrieved_at=now_iso,
                source_status="official",
            ),
            SourceRecord(
                title="FAO Wheat Crop Management Guide",
                url="https://www.fao.org/agriculture/crops/thematic-sitemap/theme/spi/wheat/en/",
                publisher="Food and Agriculture Organization (FAO)",
                retrieved_at=now_iso,
                source_status="supporting",
            ),
        ]

        # ─── 9. Crop details block ───
        crop_details = CropDetails(
            crop_type=crop_type,
            growth_stage=resolved_stage if resolved_stage in VALID_GROWTH_STAGES else "unknown",
            days_since_sowing=days_since_sowing,
            days_since_irrigation=days_since_irrigation,
            sowing_date=sowing_date,
            reported_symptoms=raw_symptoms,
            stress_indicators=matched_symptom_keys,
            stress_severity=stress_severity,
            recommended_checks_count=len(checks),
            next_stage_expected_days=next_stage_in_days,
        )

        # ─── 10. AI enhancement (Urdu / Roman Urdu) ───
        ai_payload = None
        if enable_ai:
            try:
                ai_payload = enhance_with_gemini({
                    "crop": crop_type,
                    "growth_stage": resolved_stage,
                    "days_since_irrigation": days_since_irrigation,
                    "symptoms": [k.replace("_", " ") for k in matched_symptom_keys],
                    "severity": stress_severity,
                    "tehsil": tehsil_or_coords or "Bahawalpur",
                })
            except Exception as e:
                logger.error(f"AI enhancement failed: {e}")
                ai_payload = get_deterministic_urdu_enhancement({
                    "crop": crop_type,
                    "growth_stage": resolved_stage,
                    "days_since_irrigation": days_since_irrigation,
                    "symptoms": [k.replace("_", " ") for k in matched_symptom_keys],
                    "severity": stress_severity,
                    "tehsil": tehsil_or_coords or "Bahawalpur",
                })

        # ─── 11. Determine status ───
        if crop_type != "wheat":
            status = "partial"
        elif force_offline:
            status = "partial"
            safety_flags.append("OFFLINE_MODE: Analysis performed from local knowledge base (no external provider call).")
        else:
            status = "complete"

        provider = (
            "gemini-3.8-flash+rules"
            if (enable_ai and os.environ.get("GEMINI_API_KEY"))
            else "rules-only"
        )

        response_dict = {
            "agent_id": "crop",
            "assessment_id": ass_id,
            "status": status,
            "summary": summary,
            "observations": observations,
            "possible_causes": possible_causes if possible_causes else ["No specific cause identified from current inputs."],
            "checks": checks,
            "evidence_band": evidence_band,
            "evidence_reason": evidence_reason,
            "sources": [s.model_dump() for s in sources],
            "provider_or_model": provider,
            "version": self.version,
            "created_at": now_iso,
            "safety_flags": safety_flags,
            "AI_ENHANCED": ai_payload,
            "crop_details": crop_details.model_dump(),
        }

        # ─── 12. Strict validation before returning ───
        validated = validate_crop_payload(response_dict)
        return validated


def get_crop_assessment(
    assessment_id: Optional[str] = None,
    crop: str = "wheat",
    growth_stage: Optional[str] = None,
    sowing_date: Optional[str] = None,
    days_since_irrigation: Optional[int] = None,
    symptoms: Optional[List[str]] = None,
    tehsil_or_coords: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience wrapper returning pure dict for orchestrator consumption."""
    agent = CropAgent(crop_type=crop)
    result = agent.analyze(
        assessment_id=assessment_id,
        crop=crop,
        growth_stage=growth_stage,
        sowing_date=sowing_date,
        days_since_irrigation=days_since_irrigation,
        symptoms=symptoms,
        tehsil_or_coords=tehsil_or_coords,
    )
    return result.model_dump()


if __name__ == "__main__":
    # CLI demo: run a sample wheat stress scenario
    print("🌾 Running KisanOS Crop Agent (Wheat, Tillering, 5 days since irrigation)...")
    sample = get_crop_assessment(
        crop="wheat",
        growth_stage="tillering",
        days_since_irrigation=5,
        symptoms=["yellowing leaves", "stunted growth"],
        tehsil_or_coords="bahawalpur_sadar",
    )
    print(json.dumps(sample, indent=2, ensure_ascii=False))
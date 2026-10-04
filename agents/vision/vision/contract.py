"""Final team-wide output contract for the KisanOS Vision Agent.

build_contract()  : internal analysis dict  -> mandatory JSON dict
error_contract()  : safe 'error' output when anything goes wrong
validate_contract(): pure-Python mirror of the backend checks (no extra packages)

The top-level keys, their order and their types are FIXED by the team lead.
Do not add, rename or remove any key.
"""
import re
import uuid
from datetime import datetime, timezone

AGENT_ID = "vision"
VERSION = "1.0"

STATUSES = ("complete", "partial", "unavailable", "error")
EVIDENCE_BANDS = ("low", "medium", "high", "not_calibrated")
SOURCE_STATUSES = ("official", "supporting", "secondary", "unverified")
PROVIDERS = ("open-meteo", "gemini", "groq", "amis", "self-hosted")   # team list; this agent only ever uses "self-hosted"

REQUIRED_KEYS = (
    "agent_id", "assessment_id", "status", "summary", "observations",
    "possible_causes", "checks", "evidence_band", "evidence_reason", "sources",
    "provider_or_model", "version", "created_at", "safety_flags",
)
SOURCE_KEYS = ("title", "url", "publisher", "retrieved_at", "source_status")

# Same word list the agent sanitiser uses (rule 4: no chemical / pesticide / dose).
FORBIDDEN = re.compile(
    r"\b(pesticide|fungicide|insecticide|herbicide|chemical|spray|sprayed|dose|dosage|ml per|kg per|"
    r"urea|dap|imidacloprid|propiconazole|tebuconazole)\b", re.I)
_ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# Safety-flag vocabulary. Names deliberately avoid the forbidden keywords above,
# so the backend keyword check can never trip on a flag name.
FLAG_UNSAFE_REMOVED = "unsafe_advice_removed"
FLAG_CONF_CAPPED = "confidence_capped"
FLAG_CLASS_DROPPED = "unrecognised_label_dropped"
FLAG_EXPERT = "expert_referral_recommended"
FLAG_NON_WHEAT = "non_wheat_image"
FLAG_QUALITY = "photo_quality_failed"
FLAG_EXCEPTION = "agent_exception"
FLAG_MODEL_MISSING = "model_not_available"          # self-hosted model files missing / broken: nothing was analysed
FLAG_INFERENCE_FAILED = "model_inference_failed"
FLAG_UNCALIBRATED = "model_score_uncalibrated"      # model scores are softmax scores, not calibrated probabilities
FLAG_LOW_SCORE = "low_model_score"
FLAG_NO_CROP_CHECK = "crop_check_not_performed"     # the classifier has no 'other crop' class

# ---------------------------------------------------------------- sources
# A source is MANDATORY in every response. The self-hosted model's own entry (from model_card.json) is
# added when it exists, and the symptom reference below is ALWAYS added. S-numbers: add the Vision Agent
# research-report sources here when ready (an entry left as None is skipped).
SOURCE_RETRIEVED_AT = "2026-10-04T00:00:00Z"          # date the reference below was looked up
SOURCE_REGISTRY = {
    "S1": {"title": "Classification of wheat diseases using deep learning networks with field and glasshouse images",
           "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10953319",
           "publisher": "PubMed Central (open-access article; Long, Hartley, Morris and Brown, John Innes Centre)",
           "retrieved_at": SOURCE_RETRIEVED_AT, "source_status": "supporting"},
    "S2": None,
}
DEFAULT_SOURCE_IDS = ("S1",)

# ---------------------------------------------------------------- class tables
LABELS = {
    "healthy_looking": "No visible symptoms",
    "yellowing": "Yellowing",
    "rust_like_pustules": "Rust-like pustules",
    "spots_or_blotches": "Spots or blotches",
    "visible_insects": "Visible insects",
    "drying": "Drying",
    "unclear": "Unclear",
}
# Hedged, non-chemical, never a diagnosis. Align wording with the research report.
CAUSES = {
    "healthy_looking": [],
    "yellowing": ["Water stress (too little or too much moisture)", "Nutrient-related stress",
                  "Early foliar disease"],
    "rust_like_pustules": ["Possible rust-type fungal disease (cannot be confirmed from a photo)"],
    "spots_or_blotches": ["Possible fungal leaf spot or blotch disease",
                          "Physical damage or environmental stress"],
    "visible_insects": ["Insect feeding or infestation (species not identified from a photo)"],
    "drying": ["Water or heat stress", "Advanced disease or pest damage", "Natural leaf ageing"],
    "unclear": ["Not enough visible detail to suggest a cause"],
}
CHECKS = {
    "healthy_looking": ["Re-check the field after a few days and take a new photo if symptoms appear"],
    "yellowing": ["Check whether older or younger leaves are yellow, and whether it is uniform or in patches",
                  "Check recent irrigation and soil moisture"],
    "rust_like_pustules": ["Rub a leaf with a finger and see if orange-brown powder comes off",
                           "Check how many plants in the field show the dots"],
    "spots_or_blotches": ["Check whether spots are on lower or upper leaves and if they are spreading",
                          "Look for the same spots on several plants"],
    "visible_insects": ["Check the underside of leaves and the plant base for insects",
                        "Estimate how many plants are affected"],
    "drying": ["Check whether drying starts at the leaf tips or covers the whole leaf",
               "Check soil moisture and the last irrigation date"],
    "unclear": ["Take a closer, sharper photo of the affected leaf in daylight"],
}
EXPERT_CHECK = "Show the affected leaf to a local agriculture expert for confirmation"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uuid(value=None) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid4())


def _dedupe(items):
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _skeleton(assessment_id, status, summary, band, reason, provider, flags):
    return {
        "agent_id": AGENT_ID,
        "assessment_id": _uuid(assessment_id),
        "status": status,
        "summary": summary,
        "observations": [],
        "possible_causes": [],
        "checks": [],
        "evidence_band": band,
        "evidence_reason": reason,
        "sources": [],
        "provider_or_model": provider,
        "version": VERSION,
        "created_at": now_iso(),
        "safety_flags": list(flags),
    }


def _sources_for(findings, model_source=None):
    """Model entry (if known) + every referenced S-source + the default symptom reference. Never empty."""
    out = []
    if model_source:
        out.append(dict(model_source))
    ids = list(DEFAULT_SOURCE_IDS)
    for f in findings:
        ids += [s.strip() for s in (f.get("source") or "").split(",") if s.strip()]
    for sid in _dedupe(ids):
        entry = SOURCE_REGISTRY.get(sid)
        if entry and entry["url"] not in [s["url"] for s in out]:
            out.append({k: entry[k] for k in SOURCE_KEYS})
    return out


def _model_text(internal):
    m = internal.get("model") or {}
    return f"model '{m.get('name', 'unknown')}' (sha256 {m.get('sha12', '?')}...)"


def build_contract(internal: dict, assessment_id=None) -> dict:
    """Map the agent's internal result onto the mandatory JSON."""
    flags = list(internal.get("_flags", []))
    status_in = internal.get("status")
    quality = internal.get("image_quality") or {}
    model_source = (internal.get("model") or {}).get("source")
    P = "self-hosted"

    # --- photo failed the quality gate: nothing was analysed
    if status_in == "needs_better_photo":
        issues = quality.get("issues", [])
        c = _skeleton(
            assessment_id, "unavailable",
            "The photo did not pass the image-quality check, so no analysis was performed. "
            "A clearer photo is needed; the Crop Agent should rely on text symptoms.",
            "not_calibrated",
            "No analysis performed: photo failed quality check (" + (", ".join(issues) or "unknown") + ").",
            P, flags + [FLAG_QUALITY])
        c["observations"] = [f"Photo issue: {i.replace('_', ' ')}" for i in issues]
        c["checks"] = list(quality.get("tips", [])) + \
            ["Describe the symptoms in text so another agent can still help"]
        c["sources"] = _sources_for([])
        return c

    # --- the self-hosted model is not installed / not usable: NOTHING is invented
    if status_in == "model_unavailable":
        c = _skeleton(
            assessment_id, "unavailable",
            "The self-hosted vision model is not available on this server, so the photo was not analysed. "
            "No example or placeholder result is shown; the Crop Agent should rely on text symptoms.",
            "not_calibrated",
            "No analysis performed: " + (internal.get("model_error") or "vision model not available") + ".",
            P, flags + [FLAG_MODEL_MISSING])
        c["observations"] = ["Photo analysis was not performed"]
        c["checks"] = ["Describe the symptoms in text so another agent can still help",
                       "Try again later, or show the plant to a local agriculture expert"]
        c["sources"] = _sources_for([])
        return c

    # --- the model says it is not wheat
    if status_in == "unsupported":
        c = _skeleton(
            assessment_id, "unavailable",
            "The photo does not appear to show a wheat crop. KisanOS supports wheat only, "
            "so no symptoms were assessed.",
            "not_calibrated", "Photo not recognised as wheat by " + _model_text(internal) + "; no symptom analysis was done.",
            P, flags + [FLAG_NON_WHEAT])
        c["observations"] = [f"Crop detected in photo: {internal.get('crop_detected') or 'unknown'}"]
        c["checks"] = ["Send a clear, close photo of a wheat leaf or plant"]
        c["sources"] = _sources_for([], model_source)
        return c

    # --- normal analysis (real model output)
    findings = internal.get("visible_findings", [])
    classes = [f["class"] for f in findings]
    names = _dedupe([LABELS[x].lower() for x in classes])
    conf = internal.get("confidence")
    band = "medium" if conf == "Medium" else "low"
    top = (internal.get("model") or {}).get("top") or []

    summary = (f"The self-hosted vision model analysed the wheat photo. Visible signs noted: {', '.join(names)}. "
               f"{internal.get('limitations', '')}")
    if internal.get("growth_stage"):
        summary += f" Farmer-reported growth stage: {internal['growth_stage']}."
    if internal.get("expert_referral"):
        summary += " Expert review is recommended."
    m = internal.get("model") or {}
    reason = (internal.get("confidence_reason") or "Photo-only analysis.") + \
        f" Produced by {_model_text(internal)}. Scores are the model's own uncalibrated softmax scores, not the chance of being right; " \
        "confidence is capped at medium."
    if not m.get("validated_locally"):
        reason += " The model has not been validated on local wheat photos."

    all_flags = flags + [FLAG_UNCALIBRATED] + ([FLAG_EXPERT] if internal.get("expert_referral") else [])
    c = _skeleton(assessment_id, "complete", summary.strip(), band, reason, P, all_flags)
    c["observations"] = [internal.get("crop_check") or "Crop check: not performed"] + \
        [f"{LABELS[f['class']]}: {f['detail']}" for f in findings]
    c["possible_causes"] = _dedupe([x for cl in classes for x in CAUSES[cl]])
    c["checks"] = _dedupe([x for cl in classes for x in CHECKS[cl]] +
                          ([EXPERT_CHECK] if internal.get("expert_referral") else []))
    c["sources"] = _sources_for(findings, model_source)
    return c


def error_contract(assessment_id=None, exc=None) -> dict:
    kind = type(exc).__name__ if exc is not None else "unknown"
    c = _skeleton(assessment_id, "error",
                  "The Vision Agent could not complete the analysis because of an internal error.",
                  "not_calibrated", f"Internal error ({kind}); no analysis was returned.",
                  "self-hosted", [FLAG_EXCEPTION])
    c["checks"] = ["Try again with a new photo", "Describe the symptoms in text so another agent can help"]
    c["sources"] = _sources_for([])
    return c


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def _is_iso(s) -> bool:
    if not isinstance(s, str) or not _ISO_Z.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def validate_contract(d) -> list:
    """Return a list of problems (empty list = valid). Mirrors the backend checks."""
    errs = []
    if not isinstance(d, dict):
        return ["output is not an object"]
    if tuple(d.keys()) != REQUIRED_KEYS:
        missing = [k for k in REQUIRED_KEYS if k not in d]
        extra = [k for k in d if k not in REQUIRED_KEYS]
        errs.append(f"keys differ from contract (missing={missing}, extra={extra}, or wrong order)")
    if d.get("agent_id") != AGENT_ID:
        errs.append("agent_id must be 'vision'")
    try:
        uuid.UUID(str(d.get("assessment_id")))
    except ValueError:
        errs.append("assessment_id is not a UUID")
    if d.get("status") not in STATUSES:
        errs.append("invalid status")
    if d.get("evidence_band") not in EVIDENCE_BANDS:
        errs.append("invalid evidence_band")
    if d.get("provider_or_model") not in PROVIDERS:
        errs.append("invalid provider_or_model")
    for k in ("summary", "evidence_reason", "version"):
        if not isinstance(d.get(k), str) or not d.get(k):
            errs.append(f"{k} must be a non-empty string")
    for k in ("observations", "possible_causes", "checks", "safety_flags"):
        v = d.get(k)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"{k} must be a list of strings")
    if not _is_iso(d.get("created_at")):
        errs.append("created_at is not ISO-8601 UTC (YYYY-MM-DDTHH:MM:SSZ)")
    srcs = d.get("sources")
    if not isinstance(srcs, list) or not srcs:
        errs.append("sources are mandatory: at least one source is required")
    else:
        for i, s in enumerate(srcs):
            if not isinstance(s, dict) or tuple(s.keys()) != SOURCE_KEYS:
                errs.append(f"sources[{i}] has wrong keys"); continue
            if not all(isinstance(s[k], str) and s[k] for k in SOURCE_KEYS):
                errs.append(f"sources[{i}] has an empty or non-string field")
            if not str(s["url"]).startswith(("http://", "https://")):
                errs.append(f"sources[{i}].url is not a URL")
            if not _is_iso(s["retrieved_at"]):
                errs.append(f"sources[{i}].retrieved_at is not ISO-8601")
            if s["source_status"] not in SOURCE_STATUSES:
                errs.append(f"sources[{i}].source_status is invalid")
    for s in _strings(d):
        if FORBIDDEN.search(s):
            errs.append("forbidden chemical/pesticide/dose keyword in output")
            break
    return errs

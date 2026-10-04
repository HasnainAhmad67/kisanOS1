"""KisanOS Vision Agent  (agents/vision/agent.py)

analyze_image(image_bytes, growth_stage=None, assessment_id=None) -> dict
    Returns the team's MANDATORY 14-field JSON (same contract as the Weather / Water / Crop / Market agents).

Flow:  photo -> quality gate -> self-hosted open-source model (model.py, ONNX Runtime, offline)
       -> map model labels to visible-sign classes -> safety sanitiser -> contract layer -> final validation.

Every finding comes from the model. There is NO placeholder / dummy output and NO cloud API: if the model
is not installed the answer is "unavailable". The agent only DESCRIBES visible signs; it never confirms a
disease and never gives chemical advice. Confidence is capped at Medium. It never raises.
"""
import re

try:
    from . import contract, model as model_mod
    from .quality import check_quality
except ImportError:                     # running directly from the agent folder
    import contract
    import model as model_mod
    from quality import check_quality

ALLOWED_CLASSES = set(contract.LABELS)
SOURCES = {  # S-numbers refer to contract.SOURCE_REGISTRY
    "healthy_looking": "S1", "yellowing": "S1", "rust_like_pustules": "S1",
    "spots_or_blotches": "S1", "visible_insects": "S1", "drying": "S1", "unclear": None,
}
LIMITATIONS = "Photo shows visible signs only; cannot confirm cause."
FORBIDDEN = contract.FORBIDDEN


def _base(status):
    return {
        "agent": "vision", "status": status, "provider": "self-hosted", "image_quality": None,
        "crop_detected": None, "crop_check": None, "visible_findings": [], "confidence": "Low",
        "confidence_reason": "", "expert_referral": False, "limitations": LIMITATIONS,
        "model": None, "model_error": None, "growth_stage": None, "_flags": [],
    }


def _flag(out, name):
    if name not in out["_flags"]:
        out["_flags"].append(name)


def _clean_text(t, fallback="", out=None):
    t = str(t or "").strip()
    if FORBIDDEN.search(t):
        if out is not None:
            _flag(out, contract.FLAG_UNSAFE_REMOVED)
        return fallback
    return t


def _clean_stage(stage):
    s = re.sub(r"[^A-Za-z \-]", "", str(stage or "")).strip()[:30]
    return "" if FORBIDDEN.search(s) else s


def _interpret(preds, m, out):
    """Turn the model's ranked (label, probability) list into findings. Pure rules - no guessing."""
    top_label, top_p = preds[0]
    out["model"] = {**m.describe(), "source": m.source_entry(), "top": [(l, round(p, 4)) for l, p in preds]}

    if top_label.strip().lower() in m.not_wheat:                  # the model has an explicit 'other crop' class
        out["status"] = "unsupported"
        out["crop_detected"] = _clean_text(top_label, "not wheat", out)
        return out
    out["crop_detected"] = "wheat"
    out["crop_check"] = ("Crop check: the model has an 'other crop' class and did not flag one" if m.not_wheat else
                         "Crop check: not performed by the model (wheat assumed from the app; only a plant-colour check was done)")
    if not m.not_wheat:
        _flag(out, contract.FLAG_NO_CROP_CHECK)

    def to_class(label):
        return m.mapping.get(label.strip().lower())

    findings = []
    cls = to_class(top_label)
    if cls is None:
        _flag(out, contract.FLAG_CLASS_DROPPED)
    if cls is None or top_p < m.min_p:
        if cls is not None:
            _flag(out, contract.FLAG_LOW_SCORE)
        findings.append({"class": "unclear",
                         "detail": f"top model label '{_clean_text(top_label, 'unknown', out)}' scored only {top_p:.2f}, too low to report",
                         "source": SOURCES["unclear"]})
    else:
        findings.append({"class": cls, "detail": f"model label '{_clean_text(top_label, 'unknown', out)}' (score {top_p:.2f})",
                         "source": SOURCES[cls]})
        for label, p in preds[1:3]:                                # a clearly competing second reading is reported too
            c2 = to_class(label)
            if c2 and p >= m.secondary_p and c2 not in {f["class"] for f in findings}:
                findings.append({"class": c2, "detail": f"also possible: model label '{_clean_text(label, 'unknown', out)}' (score {p:.2f})",
                                 "source": SOURCES[c2]})
    out["visible_findings"] = findings

    strong = findings[0]["class"] != "unclear" and top_p >= m.medium_p
    out["confidence"] = "Medium" if strong else "Low"                # never High
    out["confidence_reason"] = (f"Top model score {top_p:.2f} "
                                + ("is at or above the medium threshold." if strong else "is below the medium threshold, or the label is unclear."))
    classes = {f["class"] for f in findings}
    out["expert_referral"] = bool("rust_like_pustules" in classes or "unclear" in classes or out["confidence"] == "Low")
    out["status"] = "ok"
    return out


def run_analysis(image_bytes: bytes, growth_stage=None) -> dict:
    """Internal step: quality gate -> self-hosted model -> interpretation. Returns the internal dict."""
    quality = check_quality(image_bytes)
    out = _base("needs_better_photo")
    out["image_quality"] = quality
    out["growth_stage"] = _clean_stage(growth_stage) or None
    if not quality["passed"]:
        out["confidence_reason"] = "Photo quality too low for analysis."
        return out

    m, err = model_mod.get_model()
    if m is None:
        out["status"], out["model_error"] = "model_unavailable", err
        return out
    try:
        preds = m.predict(image_bytes)
    except Exception as e:                                           # a model that fails must not produce a result
        out["status"], out["model_error"] = "model_unavailable", f"inference failed ({type(e).__name__})"
        _flag(out, contract.FLAG_INFERENCE_FAILED)
        return out
    return _interpret(preds, m, out)


def analyze_image(image_bytes: bytes, growth_stage=None, assessment_id=None) -> dict:
    """PUBLIC entry point. Always returns the mandatory team JSON, never raises."""
    try:
        if not isinstance(image_bytes, (bytes, bytearray)):
            raise TypeError("image_bytes must be bytes")
        result = contract.build_contract(run_analysis(bytes(image_bytes), growth_stage), assessment_id)
        problems = contract.validate_contract(result)
        if problems:                                                 # last line of defence
            raise ValueError("; ".join(problems))
        return result
    except Exception as e:                                           # safe fallback for the backend
        return contract.error_contract(assessment_id, e)

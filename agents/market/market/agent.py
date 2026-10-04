"""KisanOS Market Agent  (agents/market/agent.py)

analyze_market(crop, location, ...) -> dict   in the MANDATORY team JSON format (same 14 fields as the Water Agent).

The agent follows this flow and builds one MARKET EVIDENCE object from it:

    MARKET AGENT
      1. Crop / produce            -> step1_crop
      2. Location / market         -> step2_location
      3. Current available price data -> step3_price_data   (a provider; the agent never invents prices)
      4. Unit                      -> step4_unit            (PKR per 40 kg / per kg / per 100 kg, always shown)
      5. Date / freshness          -> step5_freshness       (fresh <= 3 days, stale <= 14 days, else too old)
      6. Source                    -> step6_source          (title, URL, publisher, status, retrieved_at)
      7. Data availability         -> step7_availability    (available | partial | unavailable)
              |
              v
      MARKET EVIDENCE  (build_market_evidence)  ->  14-field JSON (evidence_to_contract)

Rules: prices are information only - no buy / sell / hold advice, no price predictions, no chemicals.
SAMPLE (mock) prices are always labelled and never shown as real mandi prices. If no real data
is usable the answer is "partial" or "unavailable". The agent never raises.
"""
import re
import uuid
from datetime import datetime, timezone

try:
    from . import ai_enhance
    from .providers import UNIT_KG, default_provider
    from .schema import AgentOutput, find_advice, find_unsafe, validate_output
except ImportError:                     # running directly from the agent folder
    import ai_enhance
    from providers import UNIT_KG, default_provider
    from schema import AgentOutput, find_advice, find_unsafe, validate_output

VERSION = "1.0"
AGENT_ID = "market"
SUPPORTED_CROPS = {"wheat": {"wheat", "gandum", "gandam", "gundum", "گندم"}}     # MVP crop
FRESH_DAYS = 3        # price this old or newer = fresh        (tunable default, not from a source)
STALE_DAYS = 14       # older than this is too old to call "current" (tunable default)
FLOW_LABELS = ["Crop / produce", "Location / market", "Current price data", "Unit",
               "Date / freshness", "Source", "Data availability"]       # the 7 evidence lines, in this order
SAMPLE_BANNER = "SAMPLE (mock) data - NOT real mandi prices"
DEMO_INPUT = {"crop": "wheat", "location": "Bahawalpur", "use_sample": True}   # runs on SAMPLE data only


def _utc(now=None):
    return now.astimezone(timezone.utc) if isinstance(now, datetime) and now.tzinfo else datetime.now(timezone.utc)


def _p(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _clean(text, n=60):
    t = re.sub(r"[^\w\s\-,.]", "", str(text or ""), flags=re.U).strip()[:n]
    return "" if (find_unsafe(t) or find_advice(t)) else t


def _key(text):
    s = str(text or "").lower().split(",")[0]
    s = re.sub(r"\b(mandi|market|city|district|tehsil|ghalla)\b", " ", s)
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s, flags=re.U)).strip()


# ---------------------------------------------------------------------------------- 1. crop
def step1_crop(crop):
    shown = _clean(crop)
    if not shown:
        return {"state": "missing", "input": "", "name": None}
    k = shown.lower()
    for name, aliases in SUPPORTED_CROPS.items():
        if k in aliases:
            return {"state": "supported", "input": shown, "name": name}
    return {"state": "unsupported", "input": shown, "name": None}


# ------------------------------------------------------------------------------ 2. location
def step2_location(location):
    shown = _clean(location)
    return {"state": "given" if _key(shown) else "missing", "input": shown, "key": _key(shown)}


# ----------------------------------------------------------------------- 3. price data
def step3_price_data(provider, crop_name, loc, now):
    out = {"records": 0, "skipped": [], "note": "", "provider_error": False, "rec": None,
           "matched_by": None, "locations": []}
    try:
        res = provider.fetch(crop_name, now)
    except Exception:                                   # a broken provider must not crash the agent
        out.update(note="the price data source failed", provider_error=True)
        return out
    out.update(records=len(res.records), skipped=list(res.skipped), note=res.note, provider_error=bool(res.error))
    out["locations"] = sorted({r["market"] for r in res.records})
    for by in ("market", "district"):                   # exact market first, then same district
        hits = [r for r in res.records if _key(r[by]) == loc["key"]] if loc["key"] else []
        if hits:
            hits.sort(key=lambda r: (r["is_sample"], -(r["price_dt"].timestamp() if r["price_dt"] else 0)))
            out["rec"], out["matched_by"] = hits[0], by
            break
    return out


# ---------------------------------------------------------------------------------- 4. unit
def step4_unit(rec):
    if rec is None:
        return None
    kg = UNIT_KG[rec["unit"]]
    return {"label": rec["unit"], "per_kg": rec["price_per_kg"],
            "text": f"PKR {rec['unit']}" + ("" if kg == 1 else f" (= PKR {_p(rec['price_per_kg'])} per kg)")}


# ------------------------------------------------------------------------ 5. date / freshness
def step5_freshness(rec, now):
    if rec is None:
        return {"state": "none", "age_days": None, "text": "not available"}
    if rec["is_sample"] or rec["price_dt"] is None:
        return {"state": "not_applicable", "age_days": None, "text": "not applicable (sample data has no real price date)"}
    age = (now.date() - rec["price_dt"].date()).days
    state = "fresh" if age <= FRESH_DAYS else "stale" if age <= STALE_DAYS else "too_old"
    when = "today" if age == 0 else f"{age} day{'s' if age != 1 else ''} old"
    label = {"fresh": "fresh", "stale": "stale", "too_old": "too old to treat as current"}[state]
    return {"state": state, "age_days": age, "text": f"{rec['price_date_text']} ({when}, {label})"}


# --------------------------------------------------------------------------------- 6. source
def step6_source(rec):
    if rec is None:
        return None
    return {"title": rec["source_title"], "url": rec["source_url"], "publisher": rec["publisher"],
            "retrieved_at": rec["retrieved_at"], "source_status": rec["source_status"]}


# ------------------------------------------------------------------------ 7. data availability
def step7_availability(crop, loc, data, fresh):
    """Return dict(state, reasons, flags, band)."""
    flags, reasons = [], []
    rec = data["rec"]
    if data["skipped"]:
        flags.append("records_skipped_invalid")
    if crop["state"] == "missing":
        return {"state": "unavailable", "reasons": ["No crop / produce was given."], "flags": flags, "band": "not_calibrated"}
    if crop["state"] == "unsupported":
        return {"state": "unavailable", "reasons": [f"Crop '{crop['input']}' is not supported; the Market Agent supports wheat only for now."],
                "flags": flags + ["unsupported_crop"], "band": "not_calibrated"}
    if loc["state"] == "missing":
        return {"state": "unavailable", "reasons": ["No location / market was given."], "flags": flags, "band": "not_calibrated"}
    if data["provider_error"]:
        return {"state": "unavailable", "reasons": [f"The price data source could not be read ({data['note']})."],
                "flags": flags + ["provider_error"], "band": "not_calibrated"}
    if data["records"] == 0:
        extra = (f" ({len(data['skipped'])} record(s) were invalid and skipped)" if data["skipped"]
                 else f" ({data['note']})" if data["note"] else "")
        return {"state": "unavailable", "reasons": [f"No real price data is available for wheat{extra}."], "flags": flags + ["no_price_data"], "band": "not_calibrated"}
    if rec is None:
        return {"state": "unavailable", "reasons": [f"No price data for '{loc['input']}'. Locations with data: {', '.join(data['locations'])}."],
                "flags": flags + ["unsupported_location"], "band": "not_calibrated"}
    if fresh["state"] == "too_old":
        return {"state": "unavailable", "reasons": [f"The latest price is {fresh['age_days']} days old (older than {STALE_DAYS} days), so it is not treated as current."],
                "flags": flags + ["stale_price_data"], "band": "not_calibrated"}
    if rec["is_sample"]:
        flags.append("sample_data_not_real")
        reasons.append("The price comes from SAMPLE (mock) data, not a real market.")
    if fresh["state"] == "stale":
        flags.append("stale_price_data")
        reasons.append(f"The price is {fresh['age_days']} days old (fresh means {FRESH_DAYS} days or less).")
    if data["matched_by"] == "district":
        flags.append("different_market_used")
        reasons.append(f"The price is for {rec['market']} market in the same district, not for '{loc['input']}' itself.")
    if rec["source_status"] in ("secondary", "unverified") and not rec["is_sample"]:
        flags.append("unverified_source")
        reasons.append(f"The source is marked '{rec['source_status']}', not official.")
    if reasons:
        return {"state": "partial", "reasons": reasons, "flags": flags,
                "band": "not_calibrated" if rec["is_sample"] else "low"}
    return {"state": "available", "reasons": [], "flags": flags,
            "band": "high" if rec["source_status"] == "official" else "medium"}


# ------------------------------------------------------------------------ MARKET EVIDENCE
def build_market_evidence(crop, location, provider=None, use_sample=False, now=None):
    """Run the 7 steps and return the MARKET EVIDENCE object (a plain dict)."""
    now = _utc(now)
    c, loc = step1_crop(crop), step2_location(location)
    if c["state"] == "supported" and loc["state"] == "given":
        data = step3_price_data(provider or default_provider(use_sample), c["name"], loc, now)
    else:
        data = {"records": 0, "skipped": [], "note": "", "provider_error": False, "rec": None, "matched_by": None, "locations": []}
    rec = data["rec"]
    unit, fresh, source = step4_unit(rec), step5_freshness(rec, now), step6_source(rec)
    avail = step7_availability(c, loc, data, fresh)
    return {"crop": c, "location": loc, "price_data": data, "unit": unit, "freshness": fresh,
            "source": source, "availability": avail, "created": now}


def _price_line(ev):
    rec = ev["price_data"]["rec"]
    if rec is None:
        return "not available"
    if ev["availability"]["state"] == "unavailable":      # e.g. too old: never label it as a current price
        return f"not available (the latest record, PKR {_p(rec['price'])}, is too old to treat as current)"
    rng = f" (range PKR {_p(rec['price_min'])}-{_p(rec['price_max'])})" if rec["price_min"] is not None and rec["price_max"] is not None else ""
    tag = "SAMPLE (mock) price - NOT a real mandi price: " if rec["is_sample"] else ""
    return f"{tag}PKR {_p(rec['price'])}{rng}"


def evidence_to_contract(ev, enhance=False, use_llm=True, assessment_id=None):
    """MARKET EVIDENCE -> the mandatory 14-field JSON (+ optional AI_ENHANCED)."""
    c, loc, data, a = ev["crop"], ev["location"], ev["price_data"], ev["availability"]
    rec, unit, fresh, source = data["rec"], ev["unit"], ev["freshness"], ev["source"]
    state = a["state"]
    status = {"available": "complete", "partial": "partial", "unavailable": "unavailable"}[state]
    crop_txt = c["name"] or c["input"] or "not given"
    market_txt = (rec["market"] if rec else loc["input"]) or "not given"
    unit_txt = unit["text"] if unit else "not available"
    why = "; ".join(a["reasons"]) if a["reasons"] else "all checks passed"

    # the 7 MARKET EVIDENCE lines, in the diagram's order
    observations = [
        f"Crop / produce: {crop_txt}" + (" (not supported)" if c["state"] == "unsupported" else ""),
        "Location / market: " + (f"{rec['market']} (matched by {data['matched_by']} name)" if rec else f"{loc['input'] or 'not given'} (no matching market in the price data)"),
        f"Current price data: {_price_line(ev)}",
        f"Unit: {unit_txt}",
        f"Date / freshness: {fresh['text']}",
        "Source: " + (f"{source['publisher']} ({source['source_status']}), retrieved {source['retrieved_at']}" if source else "none"),
        f"Data availability: {state}" + (f" - {why}" if a["reasons"] else ""),
    ]

    # summary (starts with the machine-readable availability)
    if rec and state != "unavailable":
        core = (f"{crop_txt.capitalize()} at {market_txt}: PKR {_p(rec['price'])} {unit['label']}"
                + ("" if UNIT_KG[unit['label']] == 1 else f" (PKR {_p(unit['per_kg'])} per kg)"))
        if rec["is_sample"]:
            summary = (f"Market data availability: partial - {SAMPLE_BANNER}. {crop_txt.capitalize()} at {market_txt}: "
                       f"sample price PKR {_p(rec['price'])} {unit['label']}; there is no real price date or source. Informational only; not trading advice.")
        else:
            summary = (f"Market data availability: {state}. {core}, price date {fresh['text']}; source: {rec['publisher']} "
                       f"({rec['source_status']}). " + (("Limits: " + " ".join(a["reasons"]) + " ") if a["reasons"] else "")
                       + "Informational only; not trading advice.")
    else:
        summary = f"Market data availability: unavailable. {' '.join(a['reasons'])} No price is shown. Informational only; not trading advice."

    # possible_causes / checks
    causes = list(a["reasons"]) or ["No data-quality issue was found. Prices still differ between markets, grades and days."]
    checks = []
    if state == "unavailable":
        checks += ["Ask your local market committee or arhti for today's rate.", "Try again later, or try a market that has price data."]
    else:
        checks.append("Confirm today's rate with your local market committee or arhti before relying on this price.")
        if fresh["state"] == "stale":
            checks.append("This price is not recent; ask for the current rate.")
        if rec and rec["is_sample"]:
            checks.append("These are sample numbers for the demo only; do not use them for any real decision.")
        if data["matched_by"] == "district":
            checks.append(f"This is the {rec['market']} market price; ask what the rate is in your own market.")
        checks.append("Compare prices only in the same unit (per 40 kg vs per kg) and the same grade / quality.")

    # evidence band + reason
    if state == "available":
        reason = (f"Exact market match; real price with a clear unit and date ({fresh['text']}); source marked '{rec['source_status']}'. "
                  f"Freshness limits (fresh <= {FRESH_DAYS} days, stale <= {STALE_DAYS} days) are tunable defaults.")
    elif state == "partial":
        reason = "Reduced because: " + " ".join(a["reasons"])
    else:
        reason = "No usable current price data: " + " ".join(a["reasons"])
    if data["skipped"] and rec:
        reason += f" {len(data['skipped'])} invalid record(s) in the data were skipped."

    flags = list(dict.fromkeys(a["flags"]))
    enhanced, provider = None, (rec["provider"] if rec and not rec["is_sample"] else "self-hosted")
    if enhance:
        facts = {"availability": state, "is_sample": bool(rec and rec["is_sample"]), "price": rec["price"] if rec and state != "unavailable" else None,
                 "unit": rec["unit"] if rec else "per 40 kg", "price_date": rec["price_date_text"] if rec else None,
                 "age_days": fresh["age_days"], "freshness": fresh["state"], "different_market": data["matched_by"] == "district"}
        enhanced, ai_provider, eflags = ai_enhance.build_ai_enhanced(facts, use_llm=use_llm)
        flags += eflags
        provider = "groq" if ai_provider == "groq" else provider

    return _envelope(status, summary, observations, causes, checks, a["band"], reason,
                     [source] if source else [], flags, provider, enhanced, assessment_id, ev["created"])


def _envelope(status, summary, observations=None, causes=None, checks=None, band="not_calibrated", reason="",
              sources=None, flags=None, provider="self-hosted", enhanced=None, assessment_id=None, created=None):
    data = {"agent_id": AGENT_ID, "assessment_id": assessment_id or str(uuid.uuid4()), "status": status,
            "summary": summary, "observations": observations or [], "possible_causes": causes or [],
            "checks": checks or [], "evidence_band": band, "evidence_reason": reason, "sources": sources or [],
            "provider_or_model": provider, "version": VERSION,
            "created_at": (created or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "safety_flags": flags or []}
    if enhanced:
        data["AI_ENHANCED"] = enhanced
    return AgentOutput(**data).model_dump(exclude_none=True)


def get_market_evidence(result: dict) -> dict:
    """Read the 7 MARKET EVIDENCE lines back out of a result (keys: crop, location, price, unit,
    date_freshness, source, availability). The mandatory format has no separate fields for them."""
    keys = dict(zip(FLOW_LABELS, ["crop", "location", "price", "unit", "date_freshness", "source", "availability"]))
    out = {}
    for line in (result or {}).get("observations", []):
        label, _, value = str(line).partition(": ")
        if label in keys:
            out[keys[label]] = value
    return out


# --------------------------------------------------------------------------- entry point
def analyze_market(crop, location, provider=None, use_sample=False, now=None, enhance=False,
                   use_llm=True, assessment_id=None) -> dict:
    """crop: e.g. "wheat" (MVP). location: market / mandi / city, e.g. "Bahawalpur".
       provider: any object with fetch(crop, now) -> ProviderResult; default = real price file from
       MARKET_PRICE_FILE, else no data. use_sample=True (or MARKET_USE_SAMPLE=1) allows the SAMPLE data,
       which is always labelled as not real. now: override the clock (tests). enhance: add AI_ENHANCED."""
    try:
        uuid.UUID(str(assessment_id))
        aid = str(assessment_id)
    except (ValueError, AttributeError, TypeError):
        aid = str(uuid.uuid4())
    try:
        if not isinstance(crop, (str, type(None))) or not isinstance(location, (str, type(None))):
            return _envelope("error", "An input value is invalid, so no market evidence was produced.",
                             checks=["Send crop and location as text, for example crop 'wheat' and location 'Bahawalpur'."],
                             reason="Invalid input type.", flags=["invalid_input"], assessment_id=aid)
        result = evidence_to_contract(build_market_evidence(crop, location, provider, use_sample, now),
                                      enhance, use_llm, aid)
        problems = validate_output(result)                    # the same checks the backend will run
        if problems:
            raise ValueError("; ".join(problems[:3]))
        return result
    except Exception as e:                                    # never crash the orchestrator
        flag = "unsafe_content_blocked" if "banned keyword" in str(e) else "agent_internal_error"
        return _envelope("error", "The Market Agent could not produce market evidence.",
                         checks=["Please try again, or ask your local market committee for the current rate."],
                         reason="Internal error; no market evidence was produced.", flags=[flag], assessment_id=aid)

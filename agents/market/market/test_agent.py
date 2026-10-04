"""Run:  python test_agent.py                       (from this agent folder)
        python -m agents.market.test_agent           (from the kisanos/ folder)
        pytest agents/market

NOTE: every price used in these tests is a made-up TEST FIXTURE. None of them is a real market price."""
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from . import ai_enhance, providers
    from .agent import DEMO_INPUT, FLOW_LABELS, analyze_market, get_market_evidence
    from .schema import find_advice, find_unsafe, validate_output
except ImportError:                     # running directly from the agent folder
    import ai_enhance
    import providers
    from agent import DEMO_INPUT, FLOW_LABELS, analyze_market, get_market_evidence
    from schema import find_advice, find_unsafe, validate_output

KEYS = ["agent_id", "assessment_id", "status", "summary", "observations", "possible_causes", "checks",
        "evidence_band", "evidence_reason", "sources", "provider_or_model", "version", "created_at", "safety_flags"]
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def rec(**kw):
    """A TEST FIXTURE record (fake numbers)."""
    base = {"crop": "wheat", "market": "Bahawalpur", "district": "Bahawalpur", "price": 3500, "price_min": 3450,
            "price_max": 3550, "unit": "PKR per 40 kg", "price_date": "2026-10-02",
            "source_title": "TEST FIXTURE daily rates", "source_url": "https://example.org/test-fixture",
            "publisher": "Test fixture publisher", "source_status": "official", "retrieved_at": "2026-10-03T08:00:00Z"}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


class Mem:                              # in-memory provider
    def __init__(self, raws): self.raws = raws
    def fetch(self, crop, now):
        records, skipped = providers._collect(self.raws, crop, now)
        return providers.ProviderResult(records, skipped, "memory test data")


@contextmanager
def env(**kw):
    old = {k: os.environ.get(k) for k in ("MARKET_PRICE_FILE", "MARKET_USE_SAMPLE")}
    for k in old:
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in kw.items() if v is not None})
    try:
        yield
    finally:
        for k, v in old.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def run(raws, crop="wheat", location="Bahawalpur", **kw):
    r = analyze_market(crop, location, provider=Mem(raws if isinstance(raws, list) else [raws]), now=NOW, **kw)
    assert validate_output(r) == [], validate_output(r)          # every output passes the backend checks
    return r


# ------------------------------------------------------------------------ the flow ----
def test_flow_has_all_seven_evidence_lines_in_order():
    for r in (run(rec()), run(rec(), crop="rice"), run([]), analyze_market(**DEMO_INPUT), run(rec(price_date="2026-09-01"))):
        labels = [o.split(": ", 1)[0] for o in r["observations"]]
        assert labels == FLOW_LABELS
        assert list(get_market_evidence(r)) == ["crop", "location", "price", "unit", "date_freshness", "source", "availability"]


def test_complete_real_official_fresh_price():
    r = run(rec())
    assert list(r.keys()) == KEYS and r["agent_id"] == "market" and r["version"] == "1.0"
    assert r["status"] == "complete" and r["evidence_band"] == "high" and r["provider_or_model"] == "self-hosted"
    ev = get_market_evidence(r)
    assert ev["crop"] == "wheat" and ev["location"].startswith("Bahawalpur") and "PKR 3500" in ev["price"]
    assert ev["unit"] == "PKR per 40 kg (= PKR 87.5 per kg)" and ev["date_freshness"] == "2026-10-02 (1 day old, fresh)"
    assert ev["availability"] == "available"
    assert r["summary"].startswith("Market data availability: available.") and "not trading advice" in r["summary"]
    assert r["sources"] == [{"title": "TEST FIXTURE daily rates", "url": "https://example.org/test-fixture",
                             "publisher": "Test fixture publisher", "retrieved_at": "2026-10-03T08:00:00Z", "source_status": "official"}]
    assert r["safety_flags"] == [] and uuid.UUID(r["assessment_id"]) and r["created_at"].endswith("Z")


def test_amis_provider_hint_and_supporting_source_band():
    assert run(rec(provider="amis"))["provider_or_model"] == "amis"
    r = run(rec(source_status="supporting"))
    assert r["status"] == "complete" and r["evidence_band"] == "medium"


# ------------------------------------------------------------------ freshness rules ----
def test_freshness_boundaries():
    def at(days):
        d = (NOW - timedelta(days=days)).strftime("%Y-%m-%d")
        return run(rec(price_date=d, retrieved_at="2026-10-03T08:00:00Z"))
    assert at(0)["status"] == "complete" and "today" in get_market_evidence(at(0))["date_freshness"]
    assert at(3)["status"] == "complete"
    for d in (4, 14):
        r = at(d)
        assert r["status"] == "partial" and r["evidence_band"] == "low" and "stale_price_data" in r["safety_flags"]
    r = at(15)
    assert r["status"] == "unavailable" and "stale_price_data" in r["safety_flags"] and "too old" in get_market_evidence(r)["date_freshness"]
    assert r["sources"]                                                       # the old record's source is kept for audit
    assert "No price is shown" in r["summary"] and "PKR" not in r["summary"]
    price = get_market_evidence(r)["price"]                                   # an old price is never labelled as current
    assert price.startswith("not available") and "too old to treat as current" in price


def test_price_date_with_time():
    r = run(rec(price_date="2026-10-03T06:30:00Z"))
    assert r["status"] == "complete" and "2026-10-03T06:30:00Z" in get_market_evidence(r)["date_freshness"]


# ------------------------------------------------------------- location handling ----
def test_location_matching_and_fallbacks():
    assert run(rec(), location="Bahawalpur Mandi")["status"] == "complete"
    assert run(rec(), location="bahawalpur, Punjab")["status"] == "complete"
    d = run(rec(market="Ahmadpur East", district="Bahawalpur"), location="Bahawalpur")      # same district only
    assert d["status"] == "partial" and "different_market_used" in d["safety_flags"] and d["evidence_band"] == "low"
    assert "Ahmadpur East" in d["summary"] and any("own market" in c for c in d["checks"])
    u = run(rec(), location="Multan")
    assert u["status"] == "unavailable" and "unsupported_location" in u["safety_flags"] and "Bahawalpur" in u["evidence_reason"]
    assert u["sources"] == [] and u["evidence_band"] == "not_calibrated"


def test_best_record_is_the_most_recent_real_one():
    r = run([rec(price=3400, price_date="2026-09-30"), rec(price=3500, price_date="2026-10-02")])
    assert "PKR 3500" in get_market_evidence(r)["price"]


# --------------------------------------------------------- unsupported / missing ----
def test_unsupported_and_missing_inputs():
    c = run(rec(), crop="rice")
    assert c["status"] == "unavailable" and "unsupported_crop" in c["safety_flags"] and c["sources"] == []
    assert "No price is shown" in c["summary"] and c["evidence_band"] == "not_calibrated"
    assert run(rec(), crop=None)["status"] == "unavailable" and run(rec(), crop="")["status"] == "unavailable"
    assert run(rec(), location=None)["status"] == "unavailable" and run(rec(), location="  ")["status"] == "unavailable"
    assert run(rec(), crop="Gandum")["status"] == "complete" and run(rec(), crop="گندم")["status"] == "complete"
    for bad in (5, ["wheat"], {"a": 1}):
        assert run(rec(), crop=bad)["status"] == "error"
        assert run(rec(), location=bad)["status"] == "error"


# ---------------------------------------------------------- missing / invalid data ----
INVALID = {
    "negative price": rec(price=-5), "zero price": rec(price=0), "text price": rec(price="abc"), "nan price": rec(price=float("nan")),
    "unknown unit": rec(unit="PKR per bag"), "unit mistake (per kg value labelled per 40 kg)": rec(price=87.5, price_min=None, price_max=None),
    "huge per-kg price": rec(price=900000, price_min=None, price_max=None), "wrong currency": rec(currency="USD"), "min above price": rec(price_min=4000),
    "no source url": rec(source_url=None), "bad source url": rec(source_url="ftp://x"), "no publisher": rec(publisher=None),
    "no retrieved_at": rec(retrieved_at=None), "retrieved before price date": rec(retrieved_at="2026-09-01T00:00:00Z"),
    "retrieved in future": rec(retrieved_at="2027-01-01T00:00:00Z"), "bad retrieved_at": rec(retrieved_at="yesterday"),
    "no price date": rec(price_date=None), "bad price date": rec(price_date="03/10/2026"), "future price date": rec(price_date="2026-12-01"),
    "bad source_status": rec(source_status="great"), "no market": rec(market=None), "no unit": rec(unit=None),
}


def test_invalid_records_are_skipped_not_shown():
    for name, bad in INVALID.items():
        r = run(bad)
        assert r["status"] == "unavailable", name
        assert "records_skipped_invalid" in r["safety_flags"] and "PKR 3" not in json.dumps(r), name
    for raw in (None, 5, "text", [1, 2]):
        assert run([raw])["status"] == "unavailable"
    ok = run([rec(price=-1), rec()])                                    # one bad + one good
    assert ok["status"] == "complete" and "records_skipped_invalid" in ok["safety_flags"] and "skipped" in ok["evidence_reason"]


def test_secondary_source_is_partial_and_unit_conversions():
    s = run(rec(source_status="secondary"))
    assert s["status"] == "partial" and "unverified_source" in s["safety_flags"] and s["evidence_band"] == "low"
    kg = get_market_evidence(run(rec(price=87.5, unit="PKR per kg", price_min=87, price_max=88)))
    assert kg["unit"] == "PKR per kg" and "PKR 87.5" in kg["price"]
    q = get_market_evidence(run(rec(price=8750, unit="Rs per quintal", price_min=8700, price_max=8800)))
    assert q["unit"] == "PKR per 100 kg (= PKR 87.5 per kg)"
    assert get_market_evidence(run(rec(unit="Rs/maund")))["unit"].startswith("PKR per 40 kg")


# --------------------------------------------------------------------- providers ----
def test_no_provider_means_unavailable_never_sample():
    with env():
        r = analyze_market("wheat", "Bahawalpur", now=NOW)
    assert r["status"] == "unavailable" and "sample" not in json.dumps(r).lower() and r["sources"] == []
    assert "no price data source is configured" in r["summary"]


def test_sample_data_is_clearly_identified():
    with env():
        r = analyze_market(**DEMO_INPUT)
    assert validate_output(r) == []
    assert r["status"] == "partial" and r["evidence_band"] == "not_calibrated" and "sample_data_not_real" in r["safety_flags"]
    assert "SAMPLE" in r["summary"] and "NOT real mandi prices" in r["summary"]
    ev = get_market_evidence(r)
    assert ev["price"].startswith("SAMPLE (mock) price - NOT a real mandi price") and "not applicable" in ev["date_freshness"]
    assert r["sources"][0]["source_status"] == "unverified" and "SAMPLE" in r["sources"][0]["title"]
    assert any("do not use them for any real decision" in c for c in r["checks"])
    with env(MARKET_USE_SAMPLE="1"):
        assert analyze_market("wheat", "Multan", now=NOW)["status"] == "partial"
    assert analyze_market("wheat", "Nowhere", use_sample=True, now=NOW)["status"] == "unavailable"


def test_file_providers_json_csv_and_errors():
    d = Path(tempfile.mkdtemp())
    (d / "p.json").write_text(json.dumps({"records": [rec()]}))
    (d / "list.json").write_text(json.dumps([rec()]))
    cols = list(rec().keys())
    (d / "p.csv").write_text(",".join(cols) + "\n" + ",".join(str(rec()[c]) for c in cols) + "\n")
    (d / "bad.json").write_text("{not json")
    for name in ("p.json", "list.json", "p.csv"):
        with env(MARKET_PRICE_FILE=str(d / name)):
            r = analyze_market("wheat", "Bahawalpur", now=NOW)
        assert r["status"] == "complete" and "PKR 3500" in get_market_evidence(r)["price"], name
    for name in ("missing.json", "bad.json"):
        with env(MARKET_PRICE_FILE=str(d / name)):
            r = analyze_market("wheat", "Bahawalpur", now=NOW)
        assert r["status"] == "unavailable" and "provider_error" in r["safety_flags"] and validate_output(r) == [], name
    with env(MARKET_PRICE_FILE=str(d / "p.json")):                         # real file wins over use_sample
        assert analyze_market("wheat", "Bahawalpur", use_sample=True, now=NOW)["status"] == "complete"


def test_broken_provider_never_crashes_the_agent():
    class Boom:
        def fetch(self, crop, now): raise RuntimeError("db down")
    for prov in (Boom(), object(), None.__class__, 5):
        r = analyze_market("wheat", "Bahawalpur", provider=prov, now=NOW)
        assert r["status"] == "unavailable" and "provider_error" in r["safety_flags"] and validate_output(r) == []


def test_template_file_is_loadable_and_has_no_records():
    t = json.loads((Path(providers.DATA_DIR) / "real_prices_TEMPLATE.json").read_text())
    assert t["records"] == [] and "record_format" in t


# --------------------------------------------------------------------- safety ----
def test_banned_words_and_trade_advice_cannot_leak():
    r = analyze_market("wheat", "Bahawalpur; spray urea 50 kg", provider=Mem([rec()]), now=NOW)
    assert validate_output(r) == [] and "urea" not in json.dumps(r).lower()
    r = analyze_market("spray urea", "Bahawalpur", provider=Mem([rec()]), now=NOW)
    assert validate_output(r) == [] and r["status"] == "unavailable"
    for field, text in (("market", "Bahawalpur spray market"), ("source_title", "You should sell now"), ("publisher", "buy now fertilizer co")):
        r = run(rec(**{field: text}))
        assert r["status"] == "unavailable" and "records_skipped_invalid" in r["safety_flags"], field
    for r in (run(rec()), run([]), analyze_market(**DEMO_INPUT)):
        assert not find_unsafe(json.dumps(r, ensure_ascii=False)) and not find_advice(json.dumps(r, ensure_ascii=False))


def test_enums_and_junk_never_raise():
    seen = set()
    for crop in ("wheat", "rice", None, 5):
        for loc in ("Bahawalpur", "Multan", "", None, ["x"]):
            for raws in ([rec()], [], [rec(price=-1)], [rec(price_date="2026-01-01")], [rec(source_status="secondary")]):
                r = run(raws, crop=crop, location=loc)
                assert r["status"] in ("complete", "partial", "unavailable", "error")
                assert r["evidence_band"] in ("low", "medium", "high", "not_calibrated")
                seen.add(r["status"])
    assert seen == {"complete", "partial", "unavailable", "error"}
    assert validate_output(analyze_market("x" * 10000, "y" * 10000, provider=Mem([rec()]), now=NOW)) == []


def test_ids_and_custom_assessment_id():
    assert run(rec())["assessment_id"] != run(rec())["assessment_id"]
    mine = str(uuid.uuid4())
    assert run(rec(), assessment_id=mine)["assessment_id"] == mine
    r = run(rec(), assessment_id="nope")
    assert r["status"] == "complete" and uuid.UUID(r["assessment_id"])


# ------------------------------------------------------------------- AI_ENHANCED ----
def test_ai_enhanced_optional_section_and_numbers_come_from_data():
    assert "AI_ENHANCED" not in run(rec())
    r = run(rec(), enhance=True, use_llm=False)
    e = r["AI_ENHANCED"]
    assert set(e) == {"urdu_summary", "roman_urdu", "audio_script_urdu", "emoji_visual", "farmer_explanation", "priority_level"}
    assert e["priority_level"] == "medium" and "3500" in e["urdu_summary"] and "3500" in e["roman_urdu"] and "2026-10-02" in e["urdu_summary"]
    s = analyze_market(**DEMO_INPUT, enhance=True, use_llm=False)["AI_ENHANCED"]
    assert "نمونہ" in s["urdu_summary"] and "farzi" in s["roman_urdu"] and "🧪" in s["emoji_visual"] and s["priority_level"] == "low"
    u = run([], enhance=True, use_llm=False)["AI_ENHANCED"]
    assert not any(ch.isdigit() for ch in u["urdu_summary"] + u["roman_urdu"]) and u["priority_level"] == "low"
    assert "AI_ENHANCED" not in run(rec(), crop=5, enhance=True)                     # error -> no enhancement


class Fake:
    def __init__(self, content=None, exc=None):
        self.content, self.exc, self.calls = content, exc, []
        outer = self
        class C:
            def create(self, **kw):
                outer.calls.append(kw)
                if outer.exc: raise outer.exc
                m = type("M", (), {"content": outer.content})()
                return type("R", (), {"choices": [type("Ch", (), {"message": m})()]})()
        self.chat = type("Chat", (), {"completions": C()})()


def with_fake(fake, fn):
    c, a = ai_enhance._client, ai_enhance.llm_available
    ai_enhance._client, ai_enhance.llm_available = (lambda: fake), (lambda: True)
    try: return fn()
    finally: ai_enhance._client, ai_enhance.llm_available = c, a


GOOD = json.dumps({"urdu_summary": "ریٹ نیچے دیے گئے ذریعے سے لیا گیا ہے۔",
                   "roman_urdu": "Rate neeche diye gaye zariye se liya gaya hai.",
                   "audio_script_urdu": "ریٹ کی تفصیل نیچے موجود ہے۔",
                   "farmer_explanation": "ریٹ ہر منڈی میں مختلف ہو سکتا ہے، اس لیے یونٹ اور تاریخ دیکھیں۔"}, ensure_ascii=False)


def test_groq_gpt_oss_120b_path_only_for_real_complete_data():
    fake = Fake("```json\n" + GOOD + "\n```")
    r = with_fake(fake, lambda: run(rec(), enhance=True))
    assert r["provider_or_model"] == "groq" and r["status"] == "complete" and validate_output(r) == []
    assert r["AI_ENHANCED"]["urdu_summary"].startswith("ریٹ نیچے") and "3500" in r["AI_ENHANCED"]["urdu_summary"]
    call = fake.calls[0]
    assert call["model"] == "openai/gpt-oss-120b"
    sent = call["messages"][1]["content"]
    assert "3500" not in sent and "Bahawalpur" not in sent and "2026" not in sent                      # model never sees price / place / date
    for fakeless in (lambda: analyze_market(**DEMO_INPUT, enhance=True),                              # sample
                     lambda: run(rec(price_date="2026-09-27"), enhance=True),                         # stale -> partial
                     lambda: run([], enhance=True)):                                                  # unavailable
        f2 = Fake(GOOD)
        r2 = with_fake(f2, fakeless)
        assert f2.calls == [] and r2["provider_or_model"] == "self-hosted"


def test_groq_unsafe_or_broken_reply_falls_back_to_templates():
    base = json.loads(GOOD)
    bad = [{**base, "urdu_summary": "ریٹ 5000 روپے ہے۔"}, {**base, "roman_urdu": "Rate 3500 hai."},
           {**base, "urdu_summary": "ابھی بیچ دیں۔"}, {**base, "roman_urdu": "Price will rise, abhi bech dein."},
           {**base, "farmer_explanation": "کھاد ڈالیں۔"}, {**base, "urdu_summary": "ریٹ دستیاب نہیں ہے۔"},
           {**base, "farmer_explanation": "english only text here"}, {"urdu_summary": "x"}]
    for b in bad:
        r = with_fake(Fake(json.dumps(b, ensure_ascii=False)), lambda: run(rec(), enhance=True))
        assert r["provider_or_model"] == "self-hosted" and "ai_output_rejected" in r["safety_flags"] and validate_output(r) == [], b
        assert "3500" in r["AI_ENHANCED"]["urdu_summary"]
    for fake in (Fake(exc=TimeoutError("slow")), Fake("not json")):
        r = with_fake(fake, lambda: run(rec(), enhance=True))
        assert r["status"] == "complete" and "ai_enhancement_unavailable" in r["safety_flags"]


# ------------------------------------------------------ the validator itself works ----
def test_validator_catches_format_violations():
    good = run(rec())
    def broke(**ch): return validate_output({**good, **ch})
    assert broke(status="done") and broke(evidence_band="very_high") and broke(created_at="03/10/2026")
    assert broke(assessment_id="123") and broke(version=1.0) and broke(observations="one") and broke(extra_field="x")
    assert broke(summary="Spray the field") and broke(summary="You should sell now") and broke(checks=["Price will rise"])
    assert broke(sources=[{"title": "t", "url": "ftp://x", "publisher": "p", "retrieved_at": "2026-10-03T00:00:00Z", "source_status": "official"}])
    assert broke(sources=[{"title": "t"}])
    missing = dict(good); missing.pop("evidence_reason")
    assert validate_output(missing)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")

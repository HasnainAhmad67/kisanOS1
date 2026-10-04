"""OPTIONAL AI_ENHANCED section (Urdu / Roman Urdu / audio script) for the Market Agent.

Groq model: openai/gpt-oss-120b.  Needs: pip install groq, and GROQ_API_KEY in your .env.
Safety design: the model is used ONLY when real, fresh, exact-market data is available, and it may only
write general wording WITHOUT any digits. The price, unit and date sentence is always built by the agent
from the data (never by the model), and sample / stale / missing data always use fixed templates.
Every model reply is checked; if anything fails, templates are used. The core agent output is never affected."""
import json
import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:                       # python-dotenv is optional
    pass

try:
    from .schema import QUANTITY, find_advice, find_unsafe
except ImportError:                     # running directly from the agent folder
    from schema import QUANTITY, find_advice, find_unsafe

MODEL = os.environ.get("MARKET_MODEL", "openai/gpt-oss-120b")
PRIORITY = {"available": "medium", "partial": "low", "unavailable": "low"}   # informational, never urgent
EMOJI = {"available": "🌾💰", "partial": "🌾💰⚠️", "unavailable": "🌾❓"}
UNIT_UR = {"per 40 kg": "فی 40 کلو", "per kg": "فی کلو", "per 100 kg": "فی 100 کلو"}
UNIT_RO = {"per 40 kg": "per 40 kg", "per kg": "per kg", "per 100 kg": "per 100 kg"}

_LEAD_UR = {"available": "ریٹ نیچے دیے گئے ذریعے سے لیا گیا ہے۔ ریٹ کی تصدیق اپنی مقامی منڈی سے کر لیں۔",
            "partial": "یہ ریٹ مکمل طور پر قابلِ بھروسا نہیں، اس لیے اپنی مقامی منڈی سے تصدیق ضرور کر لیں۔",
            "unavailable": "اس وقت اس منڈی کا قابلِ اعتماد ریٹ دستیاب نہیں۔ اپنی مقامی منڈی یا مارکیٹ کمیٹی سے ریٹ پوچھ لیں۔"}
_LEAD_RO = {"available": "Rate neeche diye gaye zariye se liya gaya hai. Rate ki tasdeeq apni muqami mandi se kar lein.",
            "partial": "Yeh rate mukammal tor par qabil-e-bharosa nahi, is liye apni muqami mandi se tasdeeq zaroor kar lein.",
            "unavailable": "Is waqt is mandi ka qabil-e-aitmaad rate dastiyab nahi. Apni muqami mandi ya market committee se rate pooch lein."}
_WHY_UR = "ریٹ ہر منڈی اور ہر دن مختلف ہو سکتا ہے، اس لیے یونٹ اور تاریخ دیکھ کر ہی موازنہ کریں۔ یہ صرف معلومات ہے، مشورہ نہیں۔"
_WHY_UR_SAMPLE = "یہ ڈیٹا صرف ڈیمو کے لیے ہے، اس پر کوئی حقیقی فیصلہ نہ کریں۔"

SYSTEM = """You are the Market Agent of KisanOS, a decision-support app for wheat farmers in Pakistan.
You receive a JSON summary about whether current market price data is available. Write short farmer-friendly
texts. IMPORTANT: the exact price, unit and date are added separately - your texts must contain NO digits at all.

Rules:
- Use ONLY facts in the summary. Never invent or mention any price, number, date or trend.
- Do NOT tell the farmer to buy, sell or hold, and do NOT predict prices. This is information only.
- Do NOT mention pesticides, fertilizer, doses or chemicals.
- Each text: 1-2 short sentences.

Reply with ONLY a JSON object, no other text:
{"urdu_summary": "<Urdu script>", "roman_urdu": "<Urdu in English letters>",
 "audio_script_urdu": "<Urdu script, easy to read aloud, starts by addressing the farmer>",
 "farmer_explanation": "<Urdu script, why checking unit and date matters>"}"""

_ARABIC = re.compile(r"[\u0600-\u06FF]")
_DIGITS = re.compile(r"[0-9\u0660-\u0669\u06F0-\u06F9]")
_SAYS_NO_DATA = re.compile(r"(دستیاب نہیں|dastiyab nahi|not available|no data)", re.I)


def llm_available() -> bool:
    if not os.environ.get("GROQ_API_KEY"):
        return False
    try:
        import groq  # noqa: F401
        return True
    except ImportError:
        return False


def _client():
    from groq import Groq
    return Groq(timeout=20.0, max_retries=1)


def _call_llm(facts: dict) -> dict:
    client = _client()
    kwargs = dict(
        model=MODEL, temperature=0.2, max_completion_tokens=2000, reasoning_effort="low",
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}],
    )
    try:
        resp = client.chat.completions.create(**kwargs)
    except TypeError:                   # older SDK without reasoning_effort
        kwargs.pop("reasoning_effort")
        resp = client.chat.completions.create(**kwargs)
    text = (resp.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def _valid(d) -> bool:
    keys = ("urdu_summary", "roman_urdu", "audio_script_urdu", "farmer_explanation")
    if not isinstance(d, dict) or any(not isinstance(d.get(k), str) for k in keys):
        return False
    for k in keys:
        t = d[k].strip()
        if not 5 <= len(t) <= 300 or _DIGITS.search(t) or find_unsafe(t) or find_advice(t) or QUANTITY.search(t):
            return False
    if not all(_ARABIC.search(d[k]) for k in ("urdu_summary", "audio_script_urdu", "farmer_explanation")):
        return False
    ro = d["roman_urdu"]
    if sum(c.isascii() for c in ro) / len(ro) < 0.95:
        return False
    return not _SAYS_NO_DATA.search(" ".join(d[k] for k in keys))


def _fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _price_sentences(f):
    """Deterministic price / unit / date sentences (Urdu, Roman Urdu). Numbers come from the data only."""
    if f["availability"] == "unavailable" or f.get("price") is None:
        return "", ""
    p, u = _fmt(f["price"]), f["unit"]
    date = f.get("price_date") or ""
    if f.get("is_sample"):
        return (f"یہ نمونہ (فرضی) ڈیٹا ہے، اصل منڈی کا ریٹ نہیں۔ نمونہ ریٹ: {p} روپے {UNIT_UR[u]}۔",
                f"Yeh namoona (farzi) data hai, asal mandi ka rate nahi. Namoona rate: {p} rupay {UNIT_RO[u]}.")
    ur = f"گندم کا ریٹ {p} روپے {UNIT_UR[u]} ہے (تاریخ: {date})۔"
    ro = f"Gandum ka rate {p} rupay {UNIT_RO[u]} hai (tareekh: {date})."
    if f.get("age_days") is not None and f.get("freshness") == "stale":
        ur += f" یہ ریٹ {f['age_days']} دن پرانا ہے، تازہ ریٹ پوچھ لیں۔"
        ro += f" Yeh rate {f['age_days']} din purana hai, taaza rate pooch lein."
    if f.get("different_market"):
        ur += " یہ ریٹ آپ کی منڈی کا نہیں بلکہ اسی ضلع کی دوسری منڈی کا ہے۔"
        ro += " Yeh rate aap ki mandi ka nahi balkay isi zile ki doosri mandi ka hai."
    return ur, ro


def build_ai_enhanced(facts: dict, use_llm: bool = True):
    """facts: availability (available|partial|unavailable), is_sample, price, unit, price_date, age_days,
    freshness, different_market. Returns (ai_enhanced_dict, provider, flags)."""
    a, flags, provider, texts = facts["availability"], [], "self-hosted", None
    eligible = a == "available" and not facts.get("is_sample")
    if eligible and use_llm:
        if llm_available():
            try:
                raw = _call_llm({"market_data_availability": a, "crop": "wheat", "unit_kind": facts["unit"],
                                 "freshness": facts.get("freshness"), "same_market": not facts.get("different_market")})
                if _valid(raw):
                    texts, provider = {k: raw[k].strip() for k in
                                       ("urdu_summary", "roman_urdu", "audio_script_urdu", "farmer_explanation")}, "groq"
                else:
                    flags.append("ai_output_rejected")
            except Exception:
                flags.append("ai_enhancement_unavailable")
        else:
            flags.append("ai_enhancement_unavailable")
    if texts is None:
        texts = {"urdu_summary": _LEAD_UR[a], "roman_urdu": _LEAD_RO[a], "audio_script_urdu": _LEAD_UR[a],
                 "farmer_explanation": _WHY_UR_SAMPLE if facts.get("is_sample") else _WHY_UR}
        if facts.get("is_sample"):                      # sample data: the first sentence must say so
            texts["urdu_summary"], texts["roman_urdu"], texts["audio_script_urdu"] = "", "", ""
    price_ur, price_ro = _price_sentences(facts)
    if facts.get("is_sample"):
        urdu, roman, audio = price_ur, price_ro, price_ur
    else:
        urdu = (texts["urdu_summary"] + " " + price_ur).strip()
        roman = (texts["roman_urdu"] + " " + price_ro).strip()
        audio = (texts["audio_script_urdu"] + " " + price_ur).strip()
    explanation = texts["farmer_explanation"] if texts["farmer_explanation"] else _WHY_UR
    emoji = EMOJI[a] + ("🧪" if facts.get("is_sample") else "")
    return {"urdu_summary": urdu, "roman_urdu": roman, "audio_script_urdu": "کسان بھائی، " + audio,
            "emoji_visual": emoji, "farmer_explanation": explanation, "priority_level": PRIORITY[a]}, provider, flags

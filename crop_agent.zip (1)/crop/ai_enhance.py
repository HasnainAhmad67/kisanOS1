"""
KisanOS — Crop Agent AI Enhancement Module
Module: agents/crop/ai_enhance.py

Provides farmer-first Urdu, Roman Urdu, and audio script generation
for wheat crop stress analysis using Google Gemini API
(or structured deterministic fallback).

Adheres strictly to KisanOS non-chemical safety policy.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Deterministic fallback (used when Gemini unavailable)
# ═══════════════════════════════════════════════════════════════
def get_deterministic_urdu_enhancement(crop_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Offline-safe Urdu/Roman Urdu generator based on rule-based templates.
    Never mentions chemicals, doses, or irrigation commands.
    """
    crop = crop_data.get("crop", "wheat")
    stage = crop_data.get("growth_stage", "unknown")
    days_irrig = crop_data.get("days_since_irrigation")
    symptoms = crop_data.get("symptoms", [])
    severity = crop_data.get("severity", "unknown")
    tehsil = crop_data.get("tehsil", "Bahawalpur")

    # ─── Priority mapping ───
    if severity == "high":
        priority = "high"
    elif severity == "moderate":
        priority = "medium"
    else:
        priority = "low"

    # ─── Emoji visual ───
    if severity == "high":
        emoji = "🌾⚠️🔍"
    elif severity == "moderate":
        emoji = "🌾🟡👀"
    else:
        emoji = "🌾✅"

    # ─── Urdu stage name ───
    stage_urdu = {
        "germination": "اگاؤ",
        "tillering": "پھٹاؤ / ٹلرنگ",
        "booting": "بوٹنگ",
        "heading": "بالی بننا",
        "flowering": "پھول",
        "grain_fill": "دانہ بھرنا",
        "maturity": "پکائی",
        "unknown": "نامعلوم",
    }.get(stage, stage)

    # ─── Symptoms in Urdu ───
    symptom_urdu_map = {
        "yellowing lower leaves": "نچلے پتوں کا پیلا پن",
        "yellowing upper leaves": "اوپر کے پتوں کا پیلا پن",
        "wilting": "پودوں کا مرجھانا",
        "stunted growth": "کمزور / چھوٹی نشوونما",
        "brown orange spots": "بھورے یا نارنجی دھبے",
        "white powdery patches": "سفید پاؤڈری دھبے",
        "chewed leaf edges": "پتوں کے کنارے کٹے ہوئے",
        "empty dry spikes": "خالی یا خشک بالیاں",
    }
    symptoms_urdu = [symptom_urdu_map.get(s, s) for s in symptoms]
    symptoms_text_urdu = "، ".join(symptoms_urdu) if symptoms_urdu else "کوئی خاص علامت نہیں"

    # ─── Urdu summary ───
    urdu_summary = (
        f"{tehsil} میں گندم کی فصل کا جائزہ: فصل {stage_urdu} کے مرحلے پر ہے۔ "
        f"کسان کی بتائی گئی علامات: {symptoms_text_urdu}۔ "
        f"شدت: {severity}۔ کیمیائی مشورے سے پہلے کھیت کا خود معائنہ کریں۔"
    )

    # ─── Roman Urdu ───
    roman_urdu = (
        f"{tehsil} mein gandum ki fasal ka jaiza: fasal {stage} stage par hai. "
        f"Kisan ki batayi hui alamaat: {', '.join(symptoms) if symptoms else 'koi khaas nahi'}. "
        f"Shiddat: {severity}. Kisi bhi chemical se pehle khud field ka muaina karein."
    )

    # ─── Spoken audio script ───
    audio_script = (
        f"السلام علیکم کسان بھائی! {tehsil} میں آپ کی گندم کی فصل کا جائزہ لیا گیا ہے۔ "
        f"آپ کی فصل {stage_urdu} کے مرحلے پر ہے۔ "
        f"آپ نے جو علامات بتائی ہیں: {symptoms_text_urdu}۔ "
        f"براہ کرم اپنے کھیت میں جا کر پتوں کا معائنہ کریں، مٹی کی نمی چیک کریں، "
        f"اور جڑوں کا رنگ دیکھیں۔ کسی بھی قسم کے کیمیکل کے استعمال سے پہلے "
        f"اپنے مقامی زراعت کے ماہر سے مشورہ کریں۔"
    )

    # ─── Farmer explanation ───
    if severity == "high":
        farmer_explanation = (
            "آپ کی فصل میں شدید علامات پائی گئی ہیں۔ فوری طور پر کھیت کا معائنہ کریں "
            "اور مقامی زراعت کے ماہر سے رابطہ کریں۔"
        )
    elif severity == "moderate":
        farmer_explanation = (
            "آپ کی فصل میں کچھ علامات پائی گئی ہیں۔ اگلے 48 گھنٹوں میں کھیت کا معائنہ کریں "
            "اور مٹی کی نمی ضرور چیک کریں۔"
        )
    else:
        farmer_explanation = (
            "آپ کی فصل فی الحال معمول کے مطابق لگ رہی ہے۔ "
            "باقاعدہ نگرانی جاری رکھیں اور مٹی کی نمی چیک کرتے رہیں۔"
        )

    return {
        "urdu_summary": urdu_summary,
        "roman_urdu": roman_urdu,
        "audio_script_urdu": audio_script,
        "emoji_visual": emoji,
        "farmer_explanation": farmer_explanation,
        "priority_level": priority,
    }


# ═══════════════════════════════════════════════════════════════
# Gemini-powered enhancement (with safety gate + fallback)
# ═══════════════════════════════════════════════════════════════
def enhance_with_gemini(crop_data: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Calls Google Gemini API to generate high-quality Urdu/Roman Urdu
    for wheat crop stress analysis.
    Strictly forbids any chemical / pesticide / dosage recommendations.
    Falls back to deterministic Urdu if API is unavailable.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return get_deterministic_urdu_enhancement(crop_data)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        prompt = f"""
You are the Urdu agricultural language adapter for KisanOS Crop Agent in Punjab, Pakistan.
Analyze this wheat (گندم) crop stress information:

- Crop: {crop_data.get('crop', 'wheat')}
- Growth Stage: {crop_data.get('growth_stage', 'unknown')}
- Days Since Last Irrigation: {crop_data.get('days_since_irrigation', 'unknown')}
- Reported Symptoms: {', '.join(crop_data.get('symptoms', [])) or 'none'}
- Severity: {crop_data.get('severity', 'unknown')}
- Location: {crop_data.get('tehsil', 'Bahawalpur')}

CRITICAL SAFETY DIRECTIVE:
1. Under NO circumstances mention any chemical names, pesticides, fungicides, fertilizers (Urea, DAP, etc.), brands, or dosages.
2. Do NOT give direct irrigation commands like "irrigate now" or exact liters/duration.
   Only suggest conservative physical inspection checks (soil moisture at root level, leaf inspection, root color check).
3. Always recommend consulting a local agriculture extension officer for any input decision.
4. Return ONLY a valid JSON object matching this exact structure:

{{
  "urdu_summary": "2-3 sentences in natural fluent Urdu",
  "roman_urdu": "2-3 sentences in simple Roman Urdu",
  "audio_script_urdu": "Conversational spoken audio script in Urdu starting with 'السلام علیکم کسان بھائی'",
  "emoji_visual": "2-3 relevant crop/weather emojis like 🌾🟡",
  "farmer_explanation": "1-2 sentences explaining why this matters for the wheat plant",
  "priority_level": "high or medium or low"
}}
"""

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        if response.text:
            cleaned = response.text.strip()
            parsed = json.loads(cleaned)

            # ─── Safety gate: reject chemical keywords ───
            forbidden = [
                "urea", "dap", "npk", "fertilizer", "pesticide", "fungicide",
                "herbicide", "insecticide", "spray", "dose", "dosage",
                "kg/acre", "ml/acre", "liters/acre", "gm/acre",
                "irrigate now", "turn on pump",
            ]
            combined = (
                str(parsed.get("urdu_summary", "")) + " " +
                str(parsed.get("roman_urdu", "")) + " " +
                str(parsed.get("farmer_explanation", "")) + " " +
                str(parsed.get("audio_script_urdu", ""))
            ).lower()

            if any(term in combined for term in forbidden):
                logger.warning("Safety gate caught forbidden term in Gemini response. Reverting to deterministic template.")
                return get_deterministic_urdu_enhancement(crop_data)

            return parsed
        else:
            return get_deterministic_urdu_enhancement(crop_data)

    except Exception as e:
        logger.warning(f"Gemini AI enhancement failed ({e}); using safe deterministic Urdu.")
        return get_deterministic_urdu_enhancement(crop_data)
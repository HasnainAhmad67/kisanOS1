"""
KisanOS — Weather Agent AI Enhancement Module
Module: agents/weather/ai_enhance.py

Provides farmer-first Urdu, Roman Urdu, and audio script generation
using Google Gemini API (or structured deterministic fallback).
Adheres strictly to KisanOS non-chemical safety policy.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Fallback generator for offline/resilience mode
def get_deterministic_urdu_enhancement(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    temp = weather_data.get("temperature_c", 26.0)
    humidity = weather_data.get("relative_humidity_pct", 55)
    rain_prob = weather_data.get("rain_probability_pct", 10)
    tehsil = weather_data.get("tehsil", "Bahawalpur")
    heat_stress = weather_data.get("heat_stress_risk", "Normal")
    rust_cond = weather_data.get("rust_favorable_condition", "Low")

    # Determine priority
    if rain_prob >= 50 or temp >= 33.0 or rust_cond == "High":
        priority = "high"
    elif rain_prob >= 25 or temp >= 30.0 or rust_cond == "Moderate":
        priority = "medium"
    else:
        priority = "low"

    # Emoji visual
    if rain_prob >= 40:
        emoji = "🌧️🌾⚠️"
    elif temp >= 32:
        emoji = "☀️🌡️🌾"
    else:
        emoji = "🌤️🌾✅"

    # Urdu summary
    urdu_summary = (
        f"{tehsil} میں درجہ حرارت {temp:.1f} ڈگری سینٹی گریڈ اور نمی {humidity} فیصد ہے۔ "
        f"اگلے چند دنوں میں بارش کا امکان {rain_prob} فیصد ہے۔ گندم کی فصل کے لیے فیلڈ نمی کی باقاعدہ جانچ رکھیں۔"
    )

    # Roman Urdu
    roman_urdu = (
        f"{tehsil} mein darja hararat {temp:.1f}°C aur nami {humidity}% hai. "
        f"Aglay dino mein barish ka imkan {rain_prob}% hai. Gandum ki fasal ke liye zameen ki nami zaroor check karein."
    )

    # Spoken Audio Script in conversational Saraiki/Urdu register for Pakistani farmers
    audio_script = (
        f"السلام علیکم کسان بھائی! {tehsil} کے موسمی جائزے کے مطابق موجودہ درجہ حرارت {temp:.0f} ڈگری ہے۔ "
        f"ہوا میں نمی {humidity} فیصد اور بارش کا امکان {rain_prob} فیصد ہے۔ "
        f"اگر آپ آبپاشی کا سوچ رہے ہیں تو پہلے مٹی کی نمی 4 انچ گہرائی پر چیک کریں اور ممکنہ بارش کا انتظار کریں۔ "
        f"صبح کے وقت پتوں پر شبنم کا جائزہ لیں۔"
    )

    # Farmer explanation
    if temp >= 32.0:
        explanation = "گندم کے دانے بننے کے مرحلے پر زیادہ گرمی دانے کے سائز پر اثر ڈال سکتی ہے، اس لیے مٹی میں مناسب نمی برقرار رکھنا ضروری ہے۔"
    elif rust_cond == "High":
        explanation = "زیادہ نمی اور معتدل درجہ حرارت میں گندم کے پتوں پر پیلی یا بھوری پھپھوندی کے نشانات کا خطرہ بڑھ جاتا ہے، فصل کا قریبی معائنہ کریں۔"
    else:
        explanation = "موسم فی الحال مستحکم ہے۔ معمول کے مطابق پودوں کی نشوونما اور کھیت کی نمی کی نگرانی جاری رکھیں۔"

    return {
        "urdu_summary": urdu_summary,
        "roman_urdu": roman_urdu,
        "audio_script_urdu": audio_script,
        "emoji_visual": emoji,
        "farmer_explanation": explanation,
        "priority_level": priority
    }


def enhance_with_gemini(weather_data: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Calls Google Gemini API (gemini-3.8-flash) to generate high quality Urdu/Roman Urdu.
    Strictly forbids any chemical product, dose, or pesticide recommendations.
    Falls back gracefully if API is unavailable.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return get_deterministic_urdu_enhancement(weather_data)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        prompt = f"""
You are the Urdu agricultural language adapter for KisanOS Weather Agent in Bahawalpur, Punjab, Pakistan.
Analyze this weather telemetry for the wheat (gandum) crop:
- Location: {weather_data.get('tehsil', 'Bahawalpur')}, Punjab
- Current Temperature: {weather_data.get('temperature_c')}°C
- Relative Humidity: {weather_data.get('relative_humidity_pct')}%
- Rain Probability: {weather_data.get('rain_probability_pct')}%
- Heat Stress Risk: {weather_data.get('heat_stress_risk')}
- Rust Favorable Condition: {weather_data.get('rust_favorable_condition')}
- 7-Day Precipitation Sum: {weather_data.get('precipitation_sum_7d', 0)} mm

CRITICAL SAFETY DIRECTIVE:
1. Under NO circumstances mention any chemical names, pesticides, fungicides, fertilizers (Urea, DAP, etc.), brands, or dosages.
2. Do NOT give direct irrigation commands like "irrigate now" or exact liters/duration. Only suggest conservative physical inspection checks (e.g. check soil moisture at root level).
3. Return ONLY a valid JSON object matching this exact structure:
{{
  "urdu_summary": "2-3 sentences in natural fluent Urdu",
  "roman_urdu": "2-3 sentences in simple Roman Urdu",
  "audio_script_urdu": "Conversational spoken audio script in Urdu starting with 'السلام علیکم کسان بھائی'",
  "emoji_visual": "2-3 relevant weather & wheat emojis like 🌤️🌾",
  "farmer_explanation": "1-2 sentences explaining why these weather conditions matter for the wheat plant",
  "priority_level": "high or medium or low"
}}
"""

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )

        if response.text:
            cleaned_text = response.text.strip()
            parsed = json.loads(cleaned_text)
            # Validate prohibited terms in AI output
            forbidden = ["urea", "dap", "spray", "pesticide", "fungicide", "dose", "ml/acre", "kg/acre"]
            combined = (str(parsed.get("urdu_summary", "")) + " " +
                        str(parsed.get("roman_urdu", "")) + " " +
                        str(parsed.get("farmer_explanation", ""))).lower()
            if any(term in combined for term in forbidden):
                logger.warning("Safety gate caught forbidden term in Gemini response. Reverting to deterministic template.")
                return get_deterministic_urdu_enhancement(weather_data)
            return parsed
        else:
            return get_deterministic_urdu_enhancement(weather_data)

    except Exception as e:
        logger.warning(f"Gemini AI enhancement failed ({e}); using safe deterministic Urdu: {e}")
        return get_deterministic_urdu_enhancement(weather_data)

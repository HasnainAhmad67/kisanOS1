from __future__ import annotations

from typing import Any


def get_deterministic_urdu_enhancement(weather: dict[str, Any]) -> dict[str, str]:
    """Compatibility helper; formats supplied measurements and never generates agronomic advice."""
    location = str(weather.get("tehsil") or weather.get("location_name") or "منتخب مقام")
    temperature = weather.get("temperature_c")
    humidity = weather.get("relative_humidity_pct")
    wind = weather.get("wind_speed_kmh")
    temp_text = f"{float(temperature):.1f}" if isinstance(temperature, (int, float)) else "دستیاب نہیں"
    humidity_text = f"{int(humidity)}" if isinstance(humidity, (int, float)) else "دستیاب نہیں"
    wind_text = f"{float(wind):.1f}" if isinstance(wind, (int, float)) else "دستیاب نہیں"

    urdu = f"{location} کے قریبی موسمی گرڈ میں درجۂ حرارت {temp_text} ڈگری سینٹی گریڈ، نمی {humidity_text} فیصد، اور ہوا کی رفتار {wind_text} کلومیٹر فی گھنٹہ ہے۔"
    roman = f"{location} ke qareebi weather grid par temperature {temp_text} degree C, humidity {humidity_text}% aur hawa {wind_text} km/h hai."
    explanation = "یہ فراہم کنندہ کے موسمی گرڈ کی معلومات ہیں، کھیت کے اندر پیمائش نہیں۔ فصل کے فیصلے سے پہلے مقامی حالات بھی دیکھیں۔"
    return {
        "urdu_summary": urdu,
        "roman_urdu": roman,
        "audio_script_urdu": "السلام علیکم۔ " + urdu + " یہ معلومات موسم کی ہیں، فصل کی تشخیص نہیں۔",
        "emoji_visual": "🌦️",
        "farmer_explanation": explanation,
        "priority_level": "low",
        "mode": "deterministic_translation",
    }


def localized_summary(
    locale: str,
    location: str,
    temperature_c: float | None,
    humidity_pct: int | None,
    wind_kmh: float | None,
    freshness: str,
) -> str:
    def value(number: float | None, unit: str) -> str:
        return f"{number:g} {unit}" if number is not None else "unavailable"

    temp = value(temperature_c, "°C")
    humidity = value(humidity_pct, "%")
    wind = value(wind_kmh, "km/h")
    if freshness != "fresh":
        if locale == "ur":
            return f"{location} کے لیے تازہ موسمی معلومات دستیاب نہیں۔ آخری محفوظ پیش گوئی پرانی ہے؛ اسے موجودہ موسم نہ سمجھیں۔"
        if locale == "roman_ur":
            return f"{location} ke liye fresh weather data available nahin. Aakhri saved forecast purana hai; ise current weather na samjhein."
        return f"Current weather data for {location} is stale or unavailable; check the freshness badge before use."
    if locale == "ur":
        return f"{location} کے قریبی موسمی گرڈ کے مطابق درجۂ حرارت {temp}، نمی {humidity} اور ہوا {wind} ہے۔ یہ کھیت کی پیمائش نہیں۔"
    if locale == "roman_ur":
        return f"{location} ke qareebi weather grid ke mutabiq temperature {temp}, humidity {humidity} aur hawa {wind} hai. Yeh khet ki measurement nahin."
    return f"At the forecast grid near {location}, temperature is {temp}, relative humidity {humidity}, and wind {wind}. This is not a field measurement."

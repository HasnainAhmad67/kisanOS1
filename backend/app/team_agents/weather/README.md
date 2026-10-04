# 🌾 KisanOS — Weather Agent (Member 1)

Autonomous real-time location-based weather & climate intelligence agent for wheat (گندم) decision support in Bahawalpur, Punjab, Pakistan.

---

## 📋 Overview & Compliance

The **Weather Agent** is an independent, non-chemical, evidence-first intelligence agent designed according to the **KisanOS World-Class Open-Source PRD v2.0** and the **Multi-Agent Contract**.

### Key Capabilities:
- 📍 **Real-time Location Granularity:** Native support for Bahawalpur pilot tehsils (*Bahawalpur Sadar, Ahmadpur East, Yazman, Hasilpur, Khairpur Tamewali*) + any custom farm coordinates.
- ⛅ **Meteorological Ingestion:** Live Open-Meteo API (temperature, relative humidity, wind speed, wind direction, precipitation probability, apparent temperature, FAO-56 Penman-Monteith reference evapotranspiration $ET_0$).
- 🌾 **Wheat Agro-Climatic Intelligence:**
  - **Seasonal Historical Baseline & Temperature Anomaly:** Evaluated against 10-year monthly Rabi wheat climate normals in Southern Punjab.
  - **Heat Stress Threshold Screening:** Real-time flagging of ambient temperatures exceeding 32°C during heading, flowering, and grain filling stages.
  - **Foliar Rust Vulnerability Index:** Evaluates conditions favorable to Stripe (Yellow) Rust (*Puccinia striiformis*) and Leaf (Brown) Rust based on relative humidity > 70% and 15–22°C temperature window.
- 🛡️ **Zero-Chemical & Zero-Prescription Guarantee:** Strictly blocks chemical product names, active ingredients, dosage rates, spray schedules, and automatic irrigation commands ("irrigate now").
- 🗣️ **Farmer-First Urdu & Roman Urdu:** Spoken audio scripts (`audio_script_urdu`), Roman Urdu summaries, and conversational explanations powered by Google Gemini (with resilient deterministic offline fallback).

---

## 📁 Folder Structure

```
agents/weather/
├── agent.py           # Main WeatherAgent class & telemetry engine
├── schema.py          # Pydantic v2 validation models & safety checks
├── ai_enhance.py      # Gemini 3.8 Flash Urdu adapter & audio script engine
├── test_agent.py      # Comprehensive 10-point test suite
├── requirements.txt   # Dependencies
└── README.md          # Technical documentation (this file)
```

---

## 🚀 Quickstart & Installation

```bash
# 1. Navigate to agent directory
cd agents/weather

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Set your Gemini API key for Urdu AI enhancement
export GEMINI_API_KEY="your-gemini-api-key"

# 4. Run the Weather Agent locally
python agent.py bahawalpur_sadar
```

---

## 🧪 Running the Test Suite

```bash
python test_agent.py
# or
pytest test_agent.py -v
```

All 10 safety and contract tests will run:
1. `test_mandatory_fields_present`: Asserts all canonical contract keys exist.
2. `test_status_enum_validity`: Validates `complete`, `partial`, `unavailable`, `error`.
3. `test_evidence_band_enum_validity`: Validates `low`, `medium`, `high`, `not_calibrated`.
4. `test_iso8601_timestamps`: Validates strict ISO-8601 timestamp compliance.
5. `test_zero_chemical_and_dosage_safety`: Ensures zero chemical/pesticide keywords.
6. `test_zero_automatic_irrigation_command`: PRD WA-02 compliance (no "irrigate now").
7. `test_sources_array_structure`: Verifies data provenance and source tiers.
8. `test_bahawalpur_pilot_locations`: Tests coordinates for all 5 Bahawalpur tehsils.
9. `test_resilient_fallback_execution`: Tests fallback when Open-Meteo is offline.
10. `test_ai_enhanced_structure`: Validates Urdu summary, Roman Urdu, and audio script.

---

## 📦 Canonical JSON Output Format

```json
{
  "agent_id": "weather",
  "assessment_id": "18c21a41-2856-4dc5-9f5a-e32569f6e6ec",
  "status": "complete",
  "summary": "Current weather in Bahawalpur Sadar is Clear sky at 26.4°C with 52% relative humidity and wind speed of 11.2 km/h. Temperature anomaly is +3.0°C compared to regional historical normals. 7-day outlook shows maximum precipitation probability of 12%, requiring conservative field soil moisture inspection.",
  "observations": [
    "Observed current air temperature of 26.4°C (Clear sky) with relative humidity at 52%.",
    "Wind velocity measured at 11.2 km/h with wind direction 195°.",
    "Current temperature (26.4°C) is within the optimal vegetative range (15-26°C) for wheat.",
    "Dry ambient conditions (52% RH) minimize foliar fungal sporulation potential."
  ],
  "possible_causes": [
    "Seasonal Rabi climatic regime in southern Punjab plain with baseline normal of 23.4°C for month 3.",
    "Subtropical anticyclonic stability influencing daytime solar radiation and surface evapotranspiration."
  ],
  "checks": [
    "Check soil moisture manually at 10 cm (4 inches) depth by squeezing a handful of soil into a ball to assess crumb cohesion before making irrigation decisions.",
    "Inspect lower leaf canopies in field corners during early morning hours for signs of moisture retention or yellowing flecks.",
    "Verify field border bund integrity to avoid unintended water loss or dry-edge stressing across field plots."
  ],
  "evidence_band": "high",
  "evidence_reason": "Fresh telemetry verified from Open-Meteo meteorological endpoints with sub-hourly updates.",
  "sources": [
    {
      "title": "Open-Meteo Global Meteorological Forecast",
      "url": "https://api.open-meteo.com/v1/forecast?latitude=29.3956&longitude=71.6836",
      "publisher": "Open-Meteo",
      "retrieved_at": "2026-10-03T12:00:00Z",
      "source_status": "official"
    },
    {
      "title": "Pakistan Meteorological Department (PMD) Regional Climatology Baseline",
      "url": "https://www.pmd.gov.pk/en/climate-data.php",
      "publisher": "Pakistan Meteorological Department",
      "retrieved_at": "2026-10-03T12:00:00Z",
      "source_status": "supporting"
    }
  ],
  "provider_or_model": "open-meteo+gemini-3.8-flash",
  "version": "1.0",
  "created_at": "2026-10-03T12:00:00Z",
  "safety_flags": [],
  "AI_ENHANCED": {
    "urdu_summary": "بہاولپور صدر میں درجہ حرارت 26.4 ڈگری اور نمی 52 فیصد ہے۔ بارش کا امکان کم ہے۔",
    "roman_urdu": "Bahawalpur Sadar mein darja hararat 26.4°C aur nami 52% hai. Barish ka imkan kam hai.",
    "audio_script_urdu": "السلام علیکم کسان بھائی! بہاولپور صدر کے موسمی جائزے کے مطابق موسم مستحکم ہے...",
    "emoji_visual": "🌤️🌾✅",
    "farmer_explanation": "موسم فی الحال مستحکم ہے۔ معمول کے مطابق پودوں کی نشوونما اور کھیت کی نمی کی باقاعدہ جانچ رکھیں۔",
    "priority_level": "low"
  }
}
```

---

## 🤝 Integration with KisanOS Backend / Orchestrator

In `backend/main.py` or the orchestrator:

```python
from agents.weather.agent import WeatherAgent

# Instantiate agent
weather_agent = WeatherAgent()

# Run for a farmer's assessment
weather_result = weather_agent.analyze(
    assessment_id=farmer_assessment["id"],
    tehsil_or_coords=farmer_assessment.get("tehsil", "bahawalpur_sadar"),
    lat=farmer_assessment.get("latitude"),
    lon=farmer_assessment.get("longitude")
)

# weather_result is a validated Pydantic model
weather_dict = weather_result.model_dump()
```

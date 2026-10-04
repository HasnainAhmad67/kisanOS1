# 🌾 KisanOS — Crop Agent (Member 4)

Wheat-specific crop stress analysis agent for KisanOS decision support in Bahawalpur, Punjab, Pakistan.

---

## 📋 Overview

The **Crop Agent** is an independent, non-chemical, evidence-first intelligence agent that analyzes wheat crop stress based on:
- Growth stage (auto-detected from sowing date OR explicit farmer input)
- Farmer-reported symptoms (yellowing, wilting, stunting, etc.)
- Days since last irrigation
- Local agro-climatic context

It strictly returns observations, possible causes, and **non-chemical field checks** — never pesticide prescriptions.

---

## 📁 Folder Structure

agents/crop/
├── agent.py           # Main CropAgent class & wheat stress knowledge base
├── schema.py          # Pydantic v2 validation models & safety gate
├── ai_enhance.py      # Gemini 3.8 Flash Urdu adapter & audio script engine
├── test_agent.py      # 20-point test suite
├── requirements.txt   # Dependencies
└── README.md          # This file

---

## 🚀 Quickstart

Step 1: Navigate to agent directory
   cd agents/crop

Step 2: Install dependencies
   pip install -r requirements.txt

Step 3: (Optional) Set Gemini API key
   export GEMINI_API_KEY="your-gemini-api-key"

Step 4: Run the Crop Agent locally
   python agent.py

---

## 🧪 Run Test Suite

python test_agent.py
or
pytest test_agent.py -v

All 20 tests validate contract compliance, safety policy, and crop logic.

---

## 🌾 Supported Wheat Growth Stages

| Stage | Days After Sowing | Key Focus |
|-------|-------------------|-----------|
| Germination | 0-15 | Emergence, sprouting |
| Tillering | 15-60 | Leaf color, tiller count |
| Booting | 60-80 | Stem elongation |
| Heading | 80-95 | Spike emergence |
| Flowering | 95-105 | Pollination, heat sensitivity |
| Grain Fill | 105-130 | Grain size, water needs |
| Maturity | 130-150 | Harvest readiness |

---

## 🔍 Supported Stress Indicators

- Yellowing lower leaves (nitrogen deficiency pattern)
- Yellowing upper leaves (sulfur/zinc deficiency)
- Wilting (water stress, root damage)
- Stunted growth (phosphorus, compaction)
- Brown/orange spots (rust — stripe & leaf)
- White powdery patches (powdery mildew)
- Chewed leaf edges (insect pest damage)
- Empty/dry spikes (heat/frost stress)

Each indicator returns possible causes, non-chemical field checks, and severity hint.

---

## 🛡️ Safety Policy

STRICTLY PROHIBITED:
- Chemical names (urea, DAP, fungicide, pesticide, etc.)
- Dosage (kg/acre, ml/acre)
- Automatic irrigation commands ("irrigate now")

ALLOWED:
- Non-chemical field inspection checks
- Soil moisture verification
- Expert referral when needed

---

## 📦 Canonical JSON Output

{
  "agent_id": "crop",
  "assessment_id": "uuid-here",
  "status": "complete",
  "summary": "...",
  "observations": ["..."],
  "possible_causes": ["..."],
  "checks": ["..."],
  "evidence_band": "medium",
  "evidence_reason": "...",
  "sources": [{"title": "PARC Guide", "url": "http://www.parc.gov.pk/", "publisher": "PARC", "retrieved_at": "2026-10-03T12:00:00Z", "source_status": "official"}],
  "provider_or_model": "rules-only",
  "version": "1.0",
  "created_at": "2026-10-03T12:00:00Z",
  "safety_flags": [],
  "AI_ENHANCED": {"urdu_summary": "...", "roman_urdu": "...", "audio_script_urdu": "...", "emoji_visual": "🌾🟡", "farmer_explanation": "...", "priority_level": "medium"},
  "crop_details": {"crop_type": "wheat", "growth_stage": "tillering", "days_since_irrigation": 5, "stress_indicators": ["yellowing_lower_leaves"], "stress_severity": "moderate"}
}

---

## 📚 Sources

- PARC Wheat Production Guide — http://www.parc.gov.pk/
- Punjab Agriculture Department — https://www.agripunjab.gov.pk/
- FAO Wheat Crop Management — https://www.fao.org/agriculture/crops/
# KisanOS Water Agent — backend-ready v2

This implementation is a deterministic, conservative water-context agent for the Bahawalpur wheat pilot. It supports the shared KisanOS result fields and includes a FastAPI adapter at `backend/app/agents/water.py`.

## Output

Both standalone and FastAPI results include `agent_id`, `assessment_id`, `status`, `summary`, `observations`, `possible_causes`, `checks`, `evidence_band`, `evidence_reason`, `sources`, `provider_or_model`, `version`, `created_at`, and `safety_flags`. The FastAPI `AgentResult` additionally carries structured `data` and `input_evidence` fields required by the existing backend.

The internal water-attention state is one of `inspect_field`, `monitor`, `recheck_after_rain`, `insufficient_information`, or `expert_review`. It is returned in the FastAPI `data.water_attention` and explained in the English summary. It is not an instruction to irrigate.

## Weather integration

The Water Agent consumes the Weather Agent's Open-Meteo 72-hour/seven-day provider panels. It uses forecast context only when the relevant product has a fresh status. Stale, missing, or conflicting weather is not used to trigger a rain-related prompt. When fresh forecast precipitation is present and drainage is explicitly good with no saturation report, the agent can ask the farmer to re-check soil moisture **after rain is actually observed**. The forecast is not treated as effective root-zone recharge. Precipitation probability is not forecast confidence.

Structured maxima and provider freshness are retained in FastAPI `data.water_context`. In the common standalone output, the agent gives concise source-attributed weather observations without adding irrigation quantities.

## PRD safeguards

- No days-since-irrigation, DAS, rainfall-mm, temperature, ET0, soil-depth, seasonal-mm, or other unapproved numeric thresholds are used for actions.
- No irrigation amount, date, frequency, duration, command, pump control, or quota is generated.
- CRI may prompt closer inspection only; it does not produce a schedule.
- Missing/uncertain stage, irrigation history, soil moisture, drainage, or fresh forecast leads to `insufficient_information` or conservative inspection.
- Farmer reports are identified as reports, not sensor measurements.
- No Groq/Gemini key is needed. The Water Agent does not call an LLM. Optional language explanation belongs after Farm Advisor.

## Standalone use

From the repository root:

```python
from agents.water.agent import analyze_water

result = analyze_water(
    crop="wheat",
    area="bahawalpur_sadar",
    growth_stage="tillering",
    irrigation_history="known",
    last_irrigation_date="2026-09-28",
    sowing_date="2026-09-15",
    soil_texture="loamy",
    soil_moisture="moist",
    drainage="good",
    weather=weather_agent_result,
)
```

Confirmed sowing date and soil texture are retained as context when provided, but they do not drive irrigation decisions. `last_irrigation_days`, `days_after_sowing`, `enhance`, and `use_llm` remain accepted only for call compatibility; they are ignored and never drive a decision. Use the actual confirmed intake fields.

## FastAPI use

The existing orchestrator call remains:

```python
assess_water(assessment_id, intake, weather_agent_result)
```

The adapter returns `app.schemas.AgentResult` and includes `data.water_attention`, `data.water_context`, `data.policy_version`, and `data.irrigation_command: null`. The policy version is `kisanos-water-conservative-v2`.

## Tests

From the repository root:

```bash
python -m pytest -q backend/tests agents/water
```

Tests use mocked provider data and do not need live weather calls or AI credentials.

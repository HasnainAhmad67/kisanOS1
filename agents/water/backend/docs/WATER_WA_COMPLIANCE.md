# Water Agent PRD Compliance — WA-01 to WA-07

**Implementation:** `kisanos-water-conservative-v2`  
**Agent result version:** `2.0.0`  
**Core:** `app.team_agents.water.agent.evaluate_water`  
**FastAPI adapter:** `app.agents.water.assess_water`

| Requirement | Implementation |
|---|---|
| WA-01 | Reads confirmed wheat and allowlisted Bahawalpur area, farmer-selected stage or unknown, sowing/DAS only as ignored context, irrigation history/date or not sure, soil moisture, drainage and Weather Agent freshness. It never substitutes an area. |
| WA-02 | `data.water_attention` is one of `inspect_field`, `monitor`, `recheck_after_rain`, `insufficient_information`, or `expert_review`. The summary/checks state the reason and ask for non-chemical field checks. No command is generated. |
| WA-03 | CRI is an inspection cue only. No schedule, date, amount or regional rule is generalized to Bahawalpur. |
| WA-04 | Does not use exact DAS, elapsed days since irrigation, rain amount, temperature, ET₀, water depth or seasonal-mm thresholds for actions. Legacy `last_irrigation_days` and `days_after_sowing` arguments are accepted for compatibility but ignored. |
| WA-05 | A `recheck_after_rain` prompt is eligible only with a fresh Open-Meteo product, forecast precipitation, explicitly good drainage, no wet-soil report, and known stage/history/moisture context. The check says to act only after rain is observed and soil is re-checked; forecast precipitation is not treated as effective recharge. |
| WA-06 | Missing/uncertain required context yields `insufficient_information`; wetness or drainage concerns yield `inspect_field`; stale/conflicting/unavailable forecast is not used. The rest of the orchestrator proceeds independently. |
| WA-07 | No unconditional irrigation instruction, amount, frequency, duration, pump/valve control, or water quota is output. `data.irrigation_command` is always `null`. |

## Shared output and FastAPI integration

The standalone `analyze_water()` returns exactly the common 14 fields: `agent_id`, `assessment_id`, `status`, `summary`, `observations`, `possible_causes`, `checks`, `evidence_band`, `evidence_reason`, `sources`, `provider_or_model`, `version`, `created_at`, and `safety_flags`.

The FastAPI adapter returns `app.schemas.AgentResult` with those same common fields and the existing backend extensions:

- `data.water_attention`
- `data.policy_version`
- `data.irrigation_command: null`
- `data.water_context` — provider, per-product freshness, optional numeric forecast facts, probability note, and recheck eligibility
- `input_evidence` — only confirmed coarse farmer inputs; no photos or free-form notes

Weather data is accepted as an `AgentResult` or serialized result. The adapter inspects product-level Open-Meteo freshness, not just an aggregate success flag, and forwards only a retrieved Open-Meteo source when fresh forecast context is actually used. Precipitation probability remains an event probability, never a confidence score.

## Privacy and model use

The Water Agent does not call Gemini or Groq and does not receive photos, farmer notes, or access tokens. Farmer-facing language explanation belongs to the post-Farm-Advisor layer. No model API key is required to run the Water Agent.

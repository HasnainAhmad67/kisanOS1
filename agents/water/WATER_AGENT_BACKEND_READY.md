# KisanOS Water Agent — backend-ready patch

This ZIP replaces the teammate Water Agent's unapproved irrigation-threshold logic with a deterministic, PRD-aligned implementation that fits the existing FastAPI `AgentResult` and Weather v3 contract. Extract it at the repository root so `agents/` and `backend/` overlay the corresponding files.

## Important safety change

The submitted Water Agent used fixed days-since-irrigation, DAS, rainfall, temperature and ET₀ thresholds and included irrigation action wording. KisanOS PRD WA-04 and WA-07 do not permit these unapproved thresholds or an irrigation command for the pilot. The replacement does not use those rules. Legacy day-count/DAS arguments are ignored. CRI may trigger closer inspection only.

## Weather integration

The backend Water adapter consumes Open-Meteo forecast products from Weather v3. It uses a rain-related prompt only when forecast data is fresh and precipitation is indicated, drainage is explicitly reported as good, wet/saturation concern is absent, and required farmer context is known. The prompt is to re-check soil moisture **after rainfall is actually observed**. It never treats forecast rain as root-zone recharge or infers an irrigation action. Stale, conflicting, or unavailable weather is not used.

## Output

The standalone agent returns the exact shared 14-field envelope. The FastAPI `AgentResult` adds its normal `data` and `input_evidence` extensions. Structured values are in `data.water_context`; `data.water_attention` uses `inspect_field`, `monitor`, `recheck_after_rain`, `insufficient_information`, or `expert_review`. `data.irrigation_command` is always `null`.

No Groq/Gemini key is needed for this agent; explanation and translation remain a later orchestration layer.

## Validate from repository root

```bash
python -m pytest -q backend/tests agents/weather agents/water
```

The tests use mocked provider responses; they make no live weather request. See `backend/docs/WATER_WA_COMPLIANCE.md` for the WA-01–WA-07 matrix and `agents/water/README.md` for interfaces.

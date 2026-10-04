# KisanOS Weather Agent — output contract patch

This focused patch updates the standalone Weather Agent and its FastAPI adapter. It does **not** replace the rest of the backend, including the main `app.schemas.AgentResult`, routes, Gemini files, `.env`, or credentials.

## Where the output appears

- **FastAPI path:** `backend/app/agents/weather.py` returns the shared `app.schemas.AgentResult` model. `agent_id` is exactly `weather`. It includes the requested common fields (`assessment_id`, `status`, `summary`, `observations`, `possible_causes`, `checks`, `evidence_band`, `evidence_reason`, `sources`, `provider_or_model`, `version`, `created_at`, and `safety_flags`) plus the established `data` and `input_evidence` extension fields.
- **Standalone package path:** `agents/weather/agent.py` and `backend/app/team_agents/weather/agent.py` return `WeatherAgentResponse` with the same common fields plus `weather_details` (and optional deterministic `AI_ENHANCED`).

Weather values remain separated by provider. PMD is used for current station observations and its 12-hour interpolated forecast; Open-Meteo provides the 72-hour and seven-day outlook. The response includes measured/forecast temperature, rainfall and precipitation-probability observations when the providers return them.

## Watch signals and interpretation

Forecast precipitation is surfaced as `weather_watch_signals` under FastAPI `data` or standalone `weather_details`. Signals report provider, horizon, forecast amount/probability and an explicit limitation. They are **not** a crop diagnosis, severity score, field measurement, official warning, or forecast-confidence score. The Weather Agent does not infer wheat damage, causal diagnosis, irrigation schedules, or treatment.

The Weather Agent may return a cautious context sentence in `possible_causes` when forecast precipitation is present. It explicitly says that weather context does not establish the cause of crop symptoms. `checks` prompts the user to compare town/grid output with actual farm conditions and consult official PMD information.

## Status note

The shared backend schema accepts `complete`, `partial`, `unavailable`, `stale`, and `error` for `AgentResult.status`. The user-provided sample lists a smaller set; this implementation keeps the additional top-level `stale` value because WX-06 requires stale data to remain explicit. Per-provider `weather_fresh`, `weather_stale`, and `weather_unavailable` statuses remain in the weather data even when the aggregate is `partial`.

## Overlay and validate

Extract this ZIP at the **repository root** so its `agents/` and `backend/` paths overlay the matching Weather files. It intentionally does not contain Gemini keys or a replacement backend schema.

From the repository root run:

```bash
python -m pytest -q backend/tests agents/weather
```

The tests are offline/mocked; they do not require live PMD/Open-Meteo requests or Gemini/Groq keys.

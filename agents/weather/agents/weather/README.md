# KisanOS Weather Agent v3.0

Weather is an evidence/provenance service for the Bahawalpur wheat pilot. It reports meteorological context only; it does **not** diagnose crops, estimate local forecast accuracy, infer farm-level conditions, or issue irrigation/treatment instructions.

## Provider contract

| Product | Provider of record | Output |
|---|---|---|
| Current station observations | PMD Flood Forecasting Division (FFD) | Source-reported temperature, humidity, rainfall (interval-neutral unless PMD specifies one), 24-hour rainfall, wind, and any optional station fields. The PMD-resolved city/station remains explicit. |
| Short horizon | PMD FFD | Its documented 12 hourly-interpolated forecast rows, with only the values PMD actually returns. |
| 72-hour forecast detail | Open-Meteo | Hourly temperature, humidity, precipitation amount/probability, wind and weather code. |
| Seven-day outlook | Open-Meteo | Daily max/min temperature, precipitation amount/probability, maximum wind and weather code. |

PMD FFD's published widget documentation describes the public JSON current endpoint, `lat`/`lng` nearest-city resolution, 12-hour interpolation and a 10-minute display refresh. Open-Meteo is called for the 72-hour and seven-day forecast only; its current conditions are not used for the FastAPI farmer-facing current card. Providers are shown in separate panels with their own retrieval/observation/run time, location resolution, timezone, units, source hash, cache age and freshness. An absent verified Open-Meteo model-run time remains null; API processing time is not substituted for it.

The public pages are <https://ffd.pmd.gov.pk/weather-widget>, <https://open-meteo.com/en/docs>, and <https://open-meteo.com/en/terms>. Recheck the provider contracts, attribution and permitted usage before public/commercial deployment. The free Open-Meteo API is currently described as non-commercial and attribution-bearing.

## Location, freshness and privacy

Only the five configured Bahawalpur pilot tehsils or a valid in-pilot coordinate pair are accepted. Unknown locations fail rather than falling back to a default. Exact farmer coordinates require `gps_consent=True` in the standalone call and the matching consent in the backend assessment. PMD identifies its nearest city; Open-Meteo identifies a nearby forecast grid. Neither is represented as field-level measurement.

Provider data with invalid or missing timestamps cannot be called fresh. PMD current observations older than six hours are withheld. When a network fetch fails, a real cached PMD value may be used only inside the six-hour limit; a forecast fallback may be shown only inside its bounded age window and is always visibly `stale`. If no valid response/cache exists, the panel is `weather_unavailable`; no synthetic weather, climatological baseline, or demo value is substituted. PMD failure does not block Open-Meteo and vice versa.

A private SQLite cache stores source payloads keyed by a one-way hash of a coarse 0.1-degree location cell and source endpoint. Exact coordinates are not stored in cached Open-Meteo payloads. The default cache path is `~/.cache/kisanos/weather.sqlite3`; file/directory permissions are restricted. PMD refresh never occurs more often than every 10 minutes. Open-Meteo refresh defaults to one hour and has a 15-minute minimum. There is no scheduled/continuous poller.

## Integration interfaces

The package supports both repository import paths:

```python
from agents.weather.agent import WeatherAgent  # public team package
# backend imports: from app.team_agents.weather.agent import WeatherAgent

agent = WeatherAgent()
report = agent.analyze(
    assessment_id="assessment-id",
    tehsil_or_coords="bahawalpur_sadar",
    enable_ai=False,
)
print(report.model_dump(mode="json"))
```

`WeatherAgent.analyze(...)` returns the legacy-compatible `WeatherAgentResponse` envelope and retains the `weather_details` and `AI_ENHANCED` property names. `fetch_live_weather(lat, lon)` and `resolve_coordinates(...)` remain available for older code. `fetch_live_weather` is a compatibility surface, not the FastAPI source for the current card.

The live API adapter is `backend/app/agents/weather.py`; its established interface remains `assess_weather(assessment_id, intake) -> app.schemas.AgentResult`. The existing orchestrator continues to persist results via its existing job/event model and to isolate each agent's failure. Weather adds nested `data.providers.pmd` and `data.providers.open_meteo` panels without changing the React-facing top-level results contract. Detailed architectural verification is in [`backend/docs/WEATHER_WX_COMPLIANCE.md`](../../backend/docs/WEATHER_WX_COMPLIANCE.md).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PMD_WEATHER_CURRENT_URL` | `https://ffd.pmd.gov.pk/weather/current` | Official PMD FFD current/12-hour JSON product; operator-controlled only. |
| `OPEN_METEO_URL` | `https://api.open-meteo.com/v1/forecast` | Open-Meteo forecast endpoint; never supplied by a farmer. |
| `WEATHER_HTTP_TIMEOUT_SECONDS` | `3.5` | Bounded request timeout per provider call. |
| `WEATHER_RETRIES` | `1` | Bounded retry count. |
| `WEATHER_CACHE_PATH` | `~/.cache/kisanos/weather.sqlite3` | Local private SQLite provider cache. |
| `PMD_MIN_REFRESH_SECONDS` | `600` | Lower-bounded at PMD's published 10-minute refresh cadence. |
| `OPEN_METEO_MIN_REFRESH_SECONDS` | `3600` | Default refresh interval; hard lower bound is 900 seconds. |
| `WEATHER_CURRENT_MAX_CACHE_AGE_SECONDS` | `21600` | Hard-capped at six hours for current conditions. |
| `WEATHER_FORECAST_MAX_CACHE_AGE_SECONDS` | `86400` | Maximum stale forecast cache age; stale is explicitly marked. |

In FastAPI, set the matching Pydantic settings documented in `backend/app/core/config.py`; Docker Compose persists the provider cache in a named volume. Do not commit `.env`, secrets, database files, or farmer data.

Gemini and Groq keys are not required or read by this Weather implementation. Urdu and Roman Urdu helper text is deterministic and tied to returned values; it makes no additional model-generated weather claims.

## Tests

Offline mocked tests cover area validation and GPS consent, PMD response and 12-hour structure, Open-Meteo forecast-only request fields, current/72-hour/seven-day outputs, source separation, invalid and stale data, provider-failure independence, location/cache privacy, Urdu output, and both integration interfaces. Run them from the repository root with:

```bash
python -m pytest -q agents/weather/test_agent.py
```

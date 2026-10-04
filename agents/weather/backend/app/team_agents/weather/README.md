# KisanOS Weather Agent v2.0

This is a drop-in refresh of the Weather agent for the Bahawalpur wheat pilot. It keeps the integration methods used by the current FastAPI backend—`resolve_coordinates(...)` and `fetch_live_weather(...)`—and maintains the familiar `WeatherAgent.analyze(...).model_dump()` interface for standalone use.

## What it does

- Resolves only the five configured Bahawalpur tehsils or a complete, valid, in-pilot coordinate pair. Exact coordinates passed to `analyze()` require `gps_consent=True`; unknown places never silently fall back to Bahawalpur Sadar.
- Requests Open-Meteo current conditions, the next 72 hours, and a seven-day outlook with explicit Asia/Karachi timezone and Celsius, km/h and mm units.
- Validates timezones, provider timestamps, response size, expected structures and numeric ranges. Missing values stay missing; the code does not fill them with a baseline.
- Reports source, provider time, server retrieval time, location granularity, units and freshness separately. Open-Meteo does not return a verified model-run time in the fields used here, so the result says that timestamp is unavailable rather than inventing one.
- Applies a maximum six-hour current-conditions age. Network failures may use a real successful cached response for up to 24 hours, always marked `stale`; older cache is not shown. No simulated weather or historical-normal “current” values are returned.
- Uses a private SQLite cache keyed by a SHA-256 hash of location and endpoint; requested coordinates and provider grid coordinates are omitted from persisted payloads. Cache directory defaults to `~/.cache/kisanos/` with restrictive permissions. Configure another path on persistent storage if needed.
- Provides fixed, deterministic Urdu and Roman Urdu wording for measured values. The `AI_ENHANCED` legacy-shaped field is a compatibility translation only—no LLM request is made, and Gemini/Groq keys are neither read nor needed.

## PRD decisions

This agent reports meteorological context only. It does **not** calculate crop heat/rust susceptibility, disease probabilities, “possible causes,” irrigation rules, provider confidence scores, or field-level measurements. Forecast probability is shown as precipitation probability—not model confidence. For PMD short-horizon observations, only integrate a machine-readable PMD source after its contract, license, location/time fields and freshness behavior have been tested; this replacement does not claim PMD data are connected.

## Install and run

From the repository root:

```bash
python -m pip install -r agents/weather/requirements.txt
python -m pytest -q agents/weather/test_agent.py
python - <<'PY'
from agents.weather.agent import WeatherAgent

report = WeatherAgent().analyze(
    assessment_id="demo-id",
    tehsil_or_coords="bahawalpur_sadar",
    enable_ai=True,  # deterministic Urdu/Roman Urdu only; no external model call
    locale="ur",
)
print(report.model_dump(mode="json"))
PY
```

If there is no network and no usable recent cache, the result is `unavailable`; the agent never manufactures a forecast. The backend API remains able to finish the overall assessment and returns its other agent cards.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `OPEN_METEO_URL` | `https://api.open-meteo.com/v1/forecast` | Operator-controlled provider endpoint; never supplied by a farmer |
| `WEATHER_HTTP_TIMEOUT_SECONDS` | `3.5` | Per-request connection/read limit |
| `WEATHER_RETRIES` | `1` | Bounded retry attempts; total provider wait stays within the backend task budget |
| `WEATHER_CACHE_PATH` | `~/.cache/kisanos/weather.sqlite3` | Private SQLite cache path |
| `WEATHER_CACHE_MAX_AGE_SECONDS` | `86400` | Maximum age for a stale-cache fallback |

Do not commit an `.env` file, provider credentials, database, or farmer data. The standard public Open-Meteo endpoint requires no key for permitted non-commercial use; check its current terms before public/commercial deployment.

## Backend integration

The replacement package deliberately preserves these backend methods:

```python
name, lat, lon, elevation = agent.resolve_coordinates(area_code, lat, lon)
data = agent.fetch_live_weather(lat, lon)
# data contains Open-Meteo's current/hourly/daily fields plus `_kisanos_weather` cache metadata.
```

This ZIP includes **both** supported import locations and the tiny backend adapter update so stale-cache provenance reaches the Weather card. Extract at the KisanOS repository root; see `WEATHER_AGENT_UPGRADE.md` in the archive root. The full standalone report is available through `analyze()`.

## Output contract

`WeatherAgentResponse` retains the common agent envelope (`agent_id`, `assessment_id`, `status`, `summary`, `observations`, `possible_causes`, `checks`, `evidence_band`, `evidence_reason`, `sources`, `provider_or_model`, `version`, `created_at`, `safety_flags`) and keeps the existing `weather_details` and `AI_ENHANCED` top-level names. Weather details use the non-agronomic current/hourly/daily fields and explicit `freshness` / `cache_status` badges. `evidence_band` is capped at `low` for fresh model-grid information and `not_calibrated` for stale information.

## Tests

The replacement tests are deterministic and use mocked provider responses, not live network access. They cover all supported areas, explicit GPS consent, API parameters/units, current/72-hour/seven-day values, cache recovery, stale/malformed provider data, cache-file permissions, translations, and backend interface compatibility.

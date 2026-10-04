# KisanOS Weather v3 — PRD and backend compliance

**Scope:** Weather is meteorological context, not field sensing, crop diagnosis, irrigation advice, or a substitute for an official warning. This note covers the implementation in `agents/weather/`, its synchronized `backend/app/team_agents/weather/` package, and the production FastAPI adapter at `backend/app/agents/weather.py`.

## WX-01 — Confirmed area, consent, and honest resolution

- The backend accepts only the pilot's configured Bahawalpur tehsils or an in-pilot coordinate pair accompanied by the assessment's explicit GPS consent. It never silently defaults an unknown location.
- Tehsil selection is a farmer-confirmed area centroid. For consented coordinates, the coordinates are passed to PMD FFD's documented `lat`/`lng` input, which resolves the nearest city. PMD city, province, station and WMO codes are returned when the source provides them. Open-Meteo is described as a nearby forecast grid.
- Every provider panel uses an explicit resolution label and `field_level_precision_claimed: false`. UI copy and evidence text state that city/station/grid data are not field measurements.
- The selected exact coordinate pair is not echoed in the result, provider source note, or logs. Weather cache keys hash a coarse 0.1-degree cell; exact provider coordinates are omitted from the cached Open-Meteo payload.

## WX-02 — Supported observations and horizons

| Product | Provider of record | Weather data exposed |
|---|---|---|
| Current conditions | PMD FFD | Source-reported temperature, relative humidity, rainfall (interval-neutral `rainfall_mm`), explicitly named 24-hour rainfall, wind speed/direction, and optional condition, dew point, pressure, visibility and station. Missing source fields stay null. | 
| Short horizon | PMD FFD | The documented twelve hourly interpolated rows, including temperature, reported rainfall and condition where supplied. No unreturned humidity/wind values are synthesized. |
| 72-hour detail | Open-Meteo | Hourly temperature, relative humidity, precipitation amount and probability, wind speed/direction and WMO code. |
| 7-day outlook | Open-Meteo | Daily max/min temperature, precipitation sum/probability maximum, max wind and WMO code. |

Temperature is Celsius, wind is km/h, precipitation is mm, probability is percent, timestamps are timezone-qualified or explicitly interpreted in the provider-declared `Asia/Karachi` timezone. The 72-hour forecast and seven-day outlook are separate from PMD's current/12-hour product.

## WX-03 — Provenance and freshness

Each provider/product panel carries provider identity and URL, retrieval time, available observation time or model-cycle/issue time, timezone, resolved location granularity, units, cache age/status, and the source snapshot SHA-256 where available. PMD's documented cycle is parsed as a UTC model-run time. Open-Meteo's `generationtime_ms` is **not** treated as a model issue/run time; absent a verified model-run field, `forecast_issue_at` is null with an explanation.

The API uses `weather_fresh`, `weather_stale`, `weather_unavailable`, and `weather_partial` on product panels, while the existing `AgentResult.status` remains within the backend's established status contract (`complete`, `partial`, `stale`, `unavailable`, `error`). Missing PMD retrieval metadata withholds current values; missing Open-Meteo retrieval metadata cannot be labeled fresh. A stale fallback retains its original retrieval timestamp and source hash, and the product shows an explicit stale status.

## WX-04 — Two-provider product separation

- **PMD FFD owns current station observations and the documented 12-hour hourly-interpolated short forecast.** The software calls the PMD FFD documented public JSON endpoint `https://ffd.pmd.gov.pk/weather/current` using the documented `lat`/`lng` parameters and displays it as its own provider panel.
- **Open-Meteo owns forecast-only 72-hour and seven-day outlook products.** The FastAPI adapter calls the hourly/daily forecast endpoint without requesting or using Open-Meteo current conditions for the farmer-facing current card.
- The existing `WeatherAgent.fetch_live_weather(...)` method remains only as a compatibility surface for old callers. The backend assessment flow does not use that method to populate current weather; current display is PMD-only.
- These public provider references do not establish local accuracy. Re-check provider terms, attribution obligations, deployment geography, and API documentation before public or commercial launch.

## WX-05 — No invented confidence or accuracy

No PMD accuracy percentage, local skill score, provider confidence, forecast confidence, or derived probability is generated. Precipitation probability is labeled only as precipitation probability, accompanied by a note that it is not forecast confidence. The Weather card uses low evidence strength for provider/weather-grid context and makes no agronomic risk interpretation.

## WX-06 — Unavailable/stale behavior and fault isolation

- Failed, malformed, oversized, invalid-timezone, or out-of-range provider data cannot be passed off as fresh or replaced with climatology/demo values. If no usable response/cache exists, the product is `weather_unavailable`; if a cached response is served, it is `weather_stale` with its original timestamp. Current observations older than six hours are withheld.
- FastAPI runs PMD and Open-Meteo independently with bounded timeouts. A failure from one provider does not suppress the other provider's card. The existing orchestration separately isolates each agent, so Weather failure cannot block Vision, Market, Water, Crop, or final job completion.
- Water/Crop policy does not convert stale or unavailable Weather into irrigation/treatment instructions. Farm Advisor detects provider-level stale flags even if the aggregate Weather card is partial.
- Weather remains an `AgentResult` producer. This repository's backend has no shared agent base class and no `AgentRun` table: intake uses `AssessmentRow`, orchestration uses existing `JobRow`/event persistence, and result retrieval keeps the established API top-level result shape. Weather-specific provenance extends only the existing card's `data` and sources.

## WX-07 — Refresh and cache limits; no polling

- PMD network refresh is no more frequent than every **600 seconds** (10 minutes), matching the official PMD widget's stated refresh cadence.
- Open-Meteo's minimum refresh interval is **900 seconds**; backend default is **3600 seconds** (one hour), below typical per-location demand while comfortably avoiding polling.
- PMD current cache fallback is hard-capped at **21,600 seconds** (six hours). Open-Meteo forecast cache fallback defaults to **86,400 seconds** (24 hours), and any use after refresh failure is visibly stale. Stale records older than their allowed windows are not shown.
- Requests happen only as part of an assessment or an explicit provider-method call. The service registers **no scheduled/continuous polling job**. SQLite cache retention is bounded; the cache file and directory use private filesystem permissions.
- A named Docker volume is configured for `/var/lib/kisanos/weather-cache`; local development defaults to `./data/weather_cache.sqlite3`.

## Existing backend integration surfaces

- **Agent interface:** no abstract base class; weather adapter is `async def assess_weather(assessment_id, intake) -> AgentResult`.
- **Pydantic result:** existing `app.schemas.AgentResult` with validated agent id, status, summary, evidence, sources, safety flags and JSON `data`. No envelope fields were renamed.
- **Persistence:** existing `AssessmentRow` and `JobRow`/events/results remain the only persistence model; no speculative `AgentRun` model was added.
- **Orchestration:** existing `app.services.orchestrator` concurrently runs Weather with other independent agents, applies its current timeout and catches per-agent failures; Water and Crop dependencies retain their current order.
- **API:** existing assessment creation/job/status/results/follow-up/delete routes are preserved. React reads Weather as the same `AgentResult` card with an expanded `data.providers` object.
- **Configuration/logging:** provider URLs, cache path, timeouts, refresh minima and age windows are settings in `app.core.config`; request IDs and privacy-conscious logging keep coordinates and provider payloads out of normal logs.
- **Imports:** public team code at `agents.weather.*`, backend modules at `app.team_agents.weather.*`, and the native FastAPI adapter import are all retained. Backend package copies are kept synchronized.

## Sources and deployment note

- PMD FFD widget documentation: <https://ffd.pmd.gov.pk/weather-widget> — documents the public JSON `weather/current` route, city resolution using `lat`/`lng`, the 12-hour hourly-interpolated forecast and 10-minute widget refresh.
- Official PMD current product: <https://ffd.pmd.gov.pk/weather/current?city=bahawalpur> (the backend uses documented `lat`/`lng` for the selected/resolved pilot area).
- Open-Meteo API docs: <https://open-meteo.com/en/docs>.
- Open-Meteo terms: <https://open-meteo.com/en/terms>. The current free API is non-commercial and attribution-bearing; public/commercial deployments must verify eligible use and suitable licensing/hosting.

The upstream pages/contracts can change; review them again before a hackathon demo with live network access and before any production rollout. Gemini and Groq credentials are not needed for this evidence/provenance implementation and are not consumed by this Weather adapter.

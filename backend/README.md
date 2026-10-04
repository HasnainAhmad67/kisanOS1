# KisanOS FastAPI backend

A Python 3.12+ backend for the Bahawalpur wheat pilot. It is evidence-first decision support—not a diagnosis, an irrigation schedule, chemical guidance, or an automated farm control system.

## What is included

- **FastAPI + Pydantic v2** typed intake/results, OpenAPI docs and field-level validation errors.
- **Explicit async agent graph**: independent Weather, Vision and Market tasks run concurrently; Crop and Water policies consume their permitted evidence; a deterministic Farm Advisor creates a short plan. Real phase events are returned—no fake progress percentages.
- **Five visible cards on every result**: Weather, Water, Crop, Vision and Market. Missing providers are marked unavailable or not assessed rather than filled with guesses.
- **PostgreSQL in Docker Compose; SQLite for quick local setup**. Each assessment is protected by a random, one-time-returned access token; only its hash is stored.
- Private, unguessable image paths; JPEG/PNG signature and dimension limits; orientation normalization and EXIF/GPS stripping; SHA-256; 24-hour default retention with a running cleanup task; delete endpoint.
- Versioned policy/source registry, job event trail, follow-ups, health/readiness endpoints and deterministic demo input scenario.

## Quick start (local)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: `http://localhost:8000/api/v1/docs`
- Liveness/readiness: `/api/v1/health/live` and `/api/v1/health/ready`
- The default SQLite file and uploaded photos live under `backend/data/` and are ignored by git.

## Docker Compose (PostgreSQL)

```bash
cd backend
cp .env.example .env
# Set POSTGRES_PASSWORD in the process environment; Compose refuses to start without it.
POSTGRES_PASSWORD='change-me-before-sharing' docker compose up --build
```

The API container runs one Uvicorn worker: this MVP's in-process task launcher and in-memory rate limiter are intentionally single-process. For multiple API replicas, replace the launcher with a durable worker/queue (e.g. PostgreSQL-backed job table + dedicated workers or Redis Streams) and move rate limiting to a shared gateway before scaling. PostgreSQL uses a persistent volume; photo storage is private and separate.

## End-to-end API flow

1. `POST /api/v1/assessments` — explicitly confirmed `wheat`, configured `area_code`, consent version, stage/context. Save the returned `assessment_id` and **access_token**; the token is not recoverable later.
2. `POST /api/v1/assessments/{id}/images` — multipart fields: `file` and `view_type` (`symptom_closeup`, `field_context`, `whole_plant`, `healthy_comparison`). Include `X-Assessment-Token`. Upload is optional; text-only assessment remains available.
3. `POST /api/v1/assessments/{id}/analyze` — returns a `job_id`.
4. Poll `GET /api/v1/jobs/{job_id}` with the assessment token. Events identify actual work and agent outcomes.
5. `GET /api/v1/assessments/{id}/results` — five independent agent envelopes plus the Farm Plan.
6. `POST /api/v1/assessments/{id}/followups` — timestamped farmer observations.
7. `DELETE /api/v1/assessments/{id}` — permanently removes metadata, job/results, follow-ups and uploaded private photos.

Use `X-Assessment-Token` on all assessment, photo, follow-up, results and job reads/writes. Do not put it in a URL. Do not send photos to external model APIs.

### Example assessment payload

```json
{
  "crop": "wheat",
  "crop_confirmed": true,
  "area_code": "bahawalpur_sadar",
  "area_confirmed": true,
  "growth_stage": "not_sure",
  "irrigation_history": "not_sure",
  "soil_moisture": "not_sure",
  "drainage": "not_sure",
  "symptom_onset": "recent",
  "symptoms_spreading": "not_sure",
  "symptoms": ["yellowing", "spots"],
  "locale": "en",
  "timezone": "Asia/Karachi",
  "consent_given": true,
  "consent_version": "2026-10-03-gemini-v1"
}
```

The supported area codes are returned by `GET /api/v1/config`. Unsupported crops, unconfirmed crop/area, out-of-pilot GPS coordinates, missing consent, or stale consent versions are rejected—not silently substituted.

## Included team code and policy gates

The original **Weather and Vision agent packages** are included unchanged under `app/team_agents/` for traceability. `app/team_agents/water/` now contains the promoted **Water Agent v2.0.0** (copied from `agents/water/agents/water/`); its legacy v1.0 tests are quarantined under `app/team_agents/water/legacy_tests/` (skipped at collection).

- **Weather**: reuses the Weather Agent's Bahawalpur location resolver and Open-Meteo fetch method. The backend deliberately does not call its `analyze()` output because its climate-risk thresholds, historical claims and fallback observations are not approved in the PRD. Only provider-reported weather values with timestamp, location granularity and freshness are normalized. If Open-Meteo fails, Weather is unavailable; no fabricated baseline is displayed.
- **Water**: runs the canonical PRD-compliant Water Agent v2.0.0 (`app/team_agents/water/agent.py`, policy `kisanos-water-conservative-v2`) through the thin adapter `app/agents/water.py`. The connected Weather adapter's `data.current` / `data.daily_outlook` / `data.freshness` output is converted into Water's dated forecast-product panels by `app/services/weather_panel.py` without inventing values; stale, partial, unavailable or missing weather reaches Water as an explicit stale/unavailable context. Allowed outputs are `inspect_field`, `monitor`, `recheck_after_rain`, `insufficient_information` and `expert_review`—never an irrigation command, amount, duration, frequency, or any pesticide/fertilizer instruction. The legacy v1.0 day/DAS/ET0/temperature thresholds remain excluded pending local agronomist approval.
- **Vision**: reuses the team's Pillow/NumPy quality gate, then only calls an operator-configured **private self-hosted** model endpoint. When none is configured, a quality-passing photo is marked `not_assessed`; the team's dummy/example result is intentionally never used. Gemini/Groq image routing is not enabled because the PRD says photos must not go to third-party inference APIs. The adapter accepts a bounded multipart request and a JSON object with `crop_detected: "wheat"`, `visible_findings: [{"class": "yellowing", "detail": "..."}]`, optional `confidence` (`low`/`medium`) and `model_version`. Unknown labels and missing/non-wheat crop results are rejected; unsafe diagnostic/action wording is rejected; confidence cannot exceed medium. A future local model plugs into `app/services/vision_inference.py::predict_locally()` — no model artifacts ship with the backend today (see `docs/VISION_AGENT.md`).
- **Crop**: `app/agents/crop.py` is a deterministic wheat-only symptom screening adapter (`crop-rules-1.1.0`, `deterministic-wheat-screening-rules`). It requires no ML model, dataset, or external service. Farmer-reported and photo-visible observations stay separate and are labelled (`farmer_reported` / `photo_visible` / `rule_based_check`); Vision output is consumed only when Vision status is `complete` or `partial`, and never as a confirmed diagnosis — if Vision is unavailable, stale, `not_assessed`, errored, or empty, Crop continues on farmer-reported symptoms only. Hypotheses use safe language only (possible water stress, possible nutrient stress, rust-like symptoms, possible leaf spots or disease, possible insect damage, premature drying; multiple causes possible); checks are non-chemical and farmer-answerable; expert review is referred for rust-like pustules, rapid spread, heading-to-grain stage with symptoms, unknown cause, low or conflicting evidence, or a farmer chemical question. Because the source registry holds no verified Crop agronomy record, cards ship `sources=[]` with an explicit unverified/provisional statement (registry id `crop-rules`). See `docs/CROP_AGENT.md`.
- **Market**: a deterministic, fail-closed adapter shows a validated, timestamped farmer-entered quote labelled `farmer_reported`, or `Price unavailable`. No AMIS scraping or synthetic/live-looking price is provided because the PRD says no stable API contract was verified. Quotes are validated (positive value, unit, market, timezone-aware observation time that is never in the future); quotes older than the configurable `MARKET_QUOTE_STALE_DAYS` (default 7 days) get a stale badge and status `stale`, and simulated quotes are tagged `SIMULATED DEMO DATA`. A future verified AMIS source plugs into `app/services/market_adapter.py::fetch_market_quote()` — nothing is fetched today and `MARKET_ADAPTER_URL` is only a readiness marker until a stable API contract is verified (see `docs/MARKET_AGENT.md`). A standalone Market team archive has arrived at `agents/market/market/` but is deliberately **not** wired in: it ships bundled sample prices and a Groq `ai_enhance.py` path that need PRD review first.
- **Farm Advisor + explanation layer**: `app/agents/advisor.py` composes a deterministic plan from validated card envelopes only — the status ladder `expert_review_recommended > insufficient_information > field_inspection_recommended > monitor`, at most 3 non-chemical checks prioritized crop → water → vision (deduplicated, each with why/how/what-to-observe), and conflicts (soil moisture vs crop signs, soil moisture vs weather precipitation, weather freshness, crop vs vision disagreement) surfaced without forcing consensus. Referral flags only escalate when the card actually assessed: `unavailable`/`stale`/`not_assessed` cards never contribute checks or findings, and the safety banner is permanent. An optional, consent-gated Gemini narration (`GEMINI_ENABLED` + `GEMINI_API_KEY` + per-assessment `gemini_explanation_consent`) rephrases the plan in farmer language; its allowlisted payload carries no photos, GPS, private notes, or agent summaries, an output safety scan rejects unsafe wording, and Gemini can never alter the Farm Plan (see `docs/FARM_ADVISOR.md`).

A standalone Crop team archive has since appeared at `agents/crop/crop/` (plus a duplicate extraction at `crop_agent.zip (1)/`), but it is deliberately **not** wired in: it emits confirmed disease/nutrient names, a numeric irrigation-gap rule, homepage-only sources with fabricated retrieval timestamps, and a Gemini `ai_enhance.py` path. Promote it only after PRD review. The Market team archive has also arrived (`agents/market/market/`) and was reviewed against `AgentResult` and the policy rules; it too is deliberately **not** wired in (see the Market bullet above). Do not connect hidden prompts or accept unvalidated text directly into the Farm Plan. Keep five card identifiers and result envelope stable.

## Configuration and secrets

`VISION_INFERENCE_URL` and optional `VISION_INFERENCE_TOKEN` are deployment-side configuration only. The URL is never accepted from a farmer. Deploy it on a private network and pin model/runtime revisions. `GEMINI_API_KEY` is read only by the optional narration explainer, which stays off unless `GEMINI_ENABLED=true` and the farmer explicitly consents per assessment (see the Farm Advisor bullet above). `GROQ_API_KEY` is not read anywhere in the gateway. Weather/water add-on LLM text and external photo inference are off; the dormant team `ai_enhance.py` modules are reachable only from their unused CLI entries. If a future policy change uses a third-party service, re-review PRD privacy, consent, retention and data-transfer terms first.

For PostgreSQL set `DATABASE_URL=postgresql+psycopg://...`. Set `ALLOW_ORIGINS` to the exact React frontend origins. Production deployments additionally need TLS at the ingress, managed secrets, encrypted storage/backups, network policy around inference, a shared durable job queue, persistent audit retention rules and dependency/container scanning.

## Demo and privacy

`POST /api/v1/demo/seed` creates a clearly labelled **SIMULATED INPUT SCENARIO** and starts a real analysis. It does not seed fake weather, price or image findings. Disable it with `DEMO_MODE=false` for public deployment. Uploaded bytes and free-text notes are never logged. Consent and image-retention terms must be reviewed before real farmer use; do not use photos for training without separate consent.

## Tests

```bash
pytest -q
```

The tests cover scope/consent, authentication, provider outage behavior, policy invariants, photo privacy, async multi-agent completion, and the Weather↔Water contract (`tests/test_weather_water_contract.py`: fresh weather is usable, stale/missing weather stays conservative, rain only yields `recheck_after_rain` without drainage risk). The bundled teammate tests are available under `app/team_agents/**/test_agent.py`; run with `pytest -q app/team_agents` after dependency installation. The legacy Water v1.0 tests under `app/team_agents/water/legacy_tests/` are quarantined and skipped because their day/DAS/ET0 threshold behavior was superseded by Water v2.0.0. Some submitted research references and unvalidated model/service artifacts require owner review before production.

## Important limitations

This is a hackathon backend foundation, not locally validated agricultural software. No accuracy or Urdu/Punjabi quality is claimed. Tehsil weather grids are not field sensors. Market prices stay unavailable absent a complete source record. Expert referral contacts, Bahawalpur symptom evidence, model licensing and extension guidance still require local review. The fifth requested team document is still missing; the Crop and Market team archives have since arrived and were reviewed but are deliberately not wired in (see above).

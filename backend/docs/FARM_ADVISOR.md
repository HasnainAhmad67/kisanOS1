# KisanOS Farm Advisor & Gemini Explanation Layer — backend integration

**Advisor:** `app/agents/advisor.py` · **Explainer:** `app/services/gemini_explainer.py`
**Shared guard:** `app/core/text_guard.py` · **Schemas:** `FarmCheck`, `FarmPlan`, `GeminiNarration`, `AIExplanation` (`app/schemas.py`)
**Tests:** `tests/test_farm_advisor.py`, `tests/test_gemini_explainer.py`

## Farm Advisor execution path

```
5 card envelopes (AgentResult) validated by policy_gate (orchestrator.py:225)
  -> build_farm_plan(assessment_id, intake, agents)   (orchestrator.py:232)
       1. gate cards by status:
            contributing = {complete, partial}
            crop-usable   = {complete, partial, unsupported}   (wheat-scope abstention may refer)
            unavailable / stale / not_assessed / error cards contribute NOTHING
       2. referrals (never a cause, only escalation):
            intake symptoms_spreading == "yes"
            crop text rust-like/pustule            (usable crop card only)
            crop.data.referral_recommended         (usable crop card only)
            water data.water_attention == expert_review   (assessed water card only)
       3. conflicts (appended, never reconciled):
            field_moisture             wet soil report vs crop water-stress overlap
            field_moisture_vs_weather  dry soil report vs provider precipitation > 0 mm
            weather_freshness          weather status stale / timestamp missing
            crop_vision_disagreement   both meaningful, no shared content word
       4. checks: crop -> water -> vision, unsafe-text screened (text_guard),
          deduplicated (casefold), capped at 3, fallback generic check
       5. status ladder:
            expert_review_recommended > insufficient_information
              > field_inspection_recommended > monitor
  -> FarmPlan (permanent safety_banner, policy_version)
```

The plan is returned in `GET /api/v1/assessments/{id}/results` with the five cards.
The Farm Advisor never generates a new agronomic fact: `rationale`,
`verification_step` and `safety_banner` are fixed strings; check titles come from
the agents' own non-chemical check text; `why`/`how_to_check`/`what_to_observe`
are fixed per-source observation scaffolding.

### Check anatomy (`FarmCheck`)

| Field | Content |
|---|---|
| `title` | the agent's check text (trimmed) |
| `how_to_check` | fixed per-source observation method (compare several plants / hand check at root depth / photo-vs-plant) |
| `why` | fixed per-source evidence context (never a cause) |
| `what_to_observe` | what to record at each spot and whether it changes |
| `evidence_labels` | `crop` / `water` / `vision` / `farmer_reported` |

### Safety rules (enforced, tested)

- No pesticide/fertilizer/dose/spray wording — candidates are re-screened with
  `text_guard.find_unsafe()` (negation-aware, so disclaimers are not rejected).
- No "irrigate now" or irrigation schedule/amount; no disease confirmation;
  no price prediction or trading language; no guarantee wording.
- `unavailable`/`stale`/`not_assessed`/`error` cards never become affirmative
  findings or contribute checks; their summaries still appear in `agent_summary`
  for transparency.
- The safety banner is always present, verbatim.
- Conflicts stay visible: the advisor never averages or hides disagreement.

## Gemini explanation execution path

```
explain_farm_plan(intake, agents, plan)   (orchestrator.py:239, wrapped in try/except)
  gates, in order (each failure -> AIExplanation skipped/unavailable, no crash):
    1. intake.gemini_explanation_consent != true  -> skipped  (consent_missing)
    2. settings.gemini_enabled is false           -> skipped  (disabled)
    3. settings.gemini_api_key empty/missing      -> unavailable (key_missing)
  4. payload = _safe_payload(...)  -> explicit allowlist, JSON only:
       locale, crop, coarse_area_code, growth_stage, symptom_codes (allowlisted),
       agent_statuses {id: status}, farm_advisor {status, rationale, checks
       [id/priority/title/why], verification_step, safety_banner}
       NO photos, NO GPS coordinates, NO private notes, NO agent summaries,
       NO raw intake, NO raw AgentResult
  5. one call: model=settings.gemini_model, temperature 0.2,
     max_output_tokens 900, response_schema=GeminiNarration,
     asyncio.timeout(settings.gemini_timeout_seconds)
  6. validation: strict schema (extra=forbid) -> count must equal len(plan.checks)
     -> non-empty after strip -> text_guard safety scan
     any failure -> AIExplanation unavailable (invalid_output), plan untouched
```

Gemini **cannot** alter the FarmPlan: only `AIExplanation` narrative fields are
returned, the plan is never passed back in, and injected extra fields are
rejected by the strict schema. Failures at every stage (timeout, invalid JSON,
schema mismatch, unsafe wording, SDK errors) degrade to `AIExplanation.status`
`skipped`/`unavailable` with a reason — the deterministic plan and the five
cards are always delivered.

## Configuration (all read live; documented in `.env.example`)

| Setting | Purpose |
|---|---|
| `GEMINI_ENABLED` (default `false`) | master switch for the narration layer |
| `GEMINI_API_KEY` | operator key; missing/blank -> `key_missing` |
| `GEMINI_MODEL` (default `gemini-3.8-flash`) | model id |
| `GEMINI_TIMEOUT_SEC` (default 10, 1–30) | per-request timeout |
| `CONSENT_VERSION` (`2026-10-03-gemini-v1`) | consent record version |

No dead or misleading config remains: `.env.example` now states that photos
stay private (they are never sent) while text narration is consent-gated.

## Sources (registry)

- `farm-advisor-policy` (`not_applicable`, no URL) — the deterministic policy
  artifact (`policy_version kisanos-safe-policy-1.0.0`); introduces no facts.
- `gemini-narration` (`not_applicable`, no URL) — provenance record for the
  optional AI narration; never a source of agronomic facts.
- Neither layer attaches fabricated citations; agronomic claims continue to
  flow only through the five agents' own card-level sources.

## Tests

`tests/test_farm_advisor.py` — ladder outcomes for all-complete, crop referral,
water `insufficient_information`/`expert_review`, vision `not_assessed` and
market `unavailable` non-blocking, stale-weather conflict, moisture-vs-weather
and crop-vs-vision conflicts, max-3 cap, deduplication, unsafe-language scan
(including the defensive check filter), safety banner, `FarmPlan` schema
round-trip, and the A4 gate (failed card + referral flag never escalates).

`tests/test_gemini_explainer.py` — every gate (consent/disabled/key/timeout),
invalid and unsafe responses rejected, valid response count-matched, payload
allowlist (no photos/GPS/notes/summaries), FarmPlan immutability under
injection attempts, negation handling, and cleanup of fake clients.

Run: `python -c "import app.main"`, `pytest -q`.

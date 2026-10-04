# Water Agent (promoted v2.0.0) - backend package

This package contains the canonical **Water Agent v2.0.0** promoted into the
backend from `agents/water/agents/water/`:

    agent.py          Water v2.0.0 core (policy kisanos-water-conservative-v2), copied verbatim
    schema.py         matching strict agent-envelope schema, copied verbatim
    ai_enhance.py     UNUSED legacy v1.0 artifact (kept only for the quarantined tests below)
    legacy_tests/     QUARANTINED legacy v1.0 tests (skipped at collection time)

The backend reaches it through the thin adapter `backend/app/agents/water.py`:

    API route -> orchestrator -> app.agents.water.assess_water
              -> app.services.weather_panel.normalize_weather_for_water
              -> app.team_agents.water.agent.evaluate_water
              -> app.schemas.AgentResult

## Policy (v2.0.0, PRD-aligned)

- Allowed attention states: `inspect_field`, `monitor`, `recheck_after_rain`,
  `insufficient_information`, `expert_review`.
- Never emits: "irrigate now", irrigation amount/duration/frequency/quota, or
  any pesticide/fertilizer/dose/spray instruction.
- No days-since-irrigation, DAS, rainfall-mm, temperature or ET0 thresholds are
  used to trigger actions; CRI yields inspection language only.
- Missing, stale or uncertain input data reduces the result to `partial` with a
  conservative attention state; `data.irrigation_command` is always `null`.

## Weather contract

Water v2.0.0 expects dated forecast products:

    data.providers.open_meteo.hourly_72h   {status, values, retrieved_at}
    data.providers.open_meteo.daily_7d     {status, values, retrieved_at}

The connected Weather adapter emits `data.current`, `data.daily_outlook` and
`data.freshness`; `backend/app/services/weather_panel.py` converts that shape
without inventing values (no hourly series is fabricated). Stale, partial or
unavailable weather reaches Water as an explicit stale/unavailable context.

## Tests

Active coverage lives in the backend test suite:

    cd backend
    pytest -q                                        # includes tests/test_weather_water_contract.py
    pytest -q app/team_agents                        # teammate suites; legacy water tests show as skipped

The legacy v1.0 tests in `legacy_tests/` assert the superseded day/DAS/ET0
threshold behavior and are skipped at module level. They are kept unchanged
for traceability only - do not "fix" them against v2.0.0.

# KisanOS Market Agent — backend integration

**Code:** `app/agents/market.py` (`market-safe-adapter-1.1.0`) · **AMIS plug-in contract:** `app/services/market_adapter.py`
**Tests:** `tests/test_market_agent.py` · **Config:** `market_quote_stale_days` (default 7), `market_adapter_url` (readiness marker)

## Execution path

```
POST /api/v1/assessments          market_quote validated by FarmerMarketQuote
    (market, value>0, unit enum, observed_at with timezone, optional simulated flag)
  -> payload stored (model_dump(mode="json"))

POST /api/v1/assessments/{id}/analyze
  -> orchestrator._run_job (app/services/orchestrator.py:203)
      -> asyncio.to_thread(assess_market, assessment_id, intake)
          1. no quote?            -> probe app.services.market_adapter.fetch_market_quote()
                                     (returns None today) -> status "unavailable",
                                     summary "Price unavailable: ...", data.quote = None
          2. validate the quote   -> positive finite value, unit present, market present,
                                     observed_at present + timezone + never in the future
                                     (any problem -> "unavailable" + data.quote_problems)
          3. freshness            -> age > market_quote_stale_days -> status "stale" + stale badge
          4. simulated flag       -> tagged "SIMULATED DEMO DATA", never "complete"
          5. otherwise            -> status "complete", Source(source_status="farmer_reported")
  -> AgentResult -> policy_gate -> results
```

The Farm Advisor does not read the Market card; no other agent consumes it.

## Fail-closed matrix

| Situation | status | shown price |
|---|---|---|
| No quote (or `market_quote: null`) | `unavailable` — "Price unavailable: …" | none (`data.quote = None`) |
| Quote fails validation (missing/invalid market, unit, value; naive/missing/future time) | `unavailable` + `data.quote_problems` codes | none |
| Valid quote older than `MARKET_QUOTE_STALE_DAYS` (default 7) | `stale` + `data.stale_badge = true` | shown, explicitly "not presented as a current price" |
| Valid fresh quote marked `simulated` | `partial` + `SIMULATED DEMO DATA` tag (`data.data_classification`) | shown only as tagged demo data |
| Valid fresh farmer quote | `complete`, `provider_or_model: farmer_reported` | shown, disclosed as not verified |
| Adapter returns a payload (never today) | unchanged — payload **not consumed** (`adapter_payload_not_used`) | none |

Validation problem codes: `quote_not_an_object`, `market_name_missing`, `value_not_a_number`,
`value_not_positive`, `value_out_of_range`, `unit_missing`, `observed_at_missing`,
`observed_at_invalid`, `observed_at_timezone_missing`, `observed_at_future`.

## AMIS adapter interface (`app/services/market_adapter.py`)

- `fetch_market_quote(market: str, crop: str) -> dict | None` — returns **`None` today**; reason reported by `adapter_status()`.
- `adapter_status()` reads `MARKET_ADAPTER_URL` so the setting is a live *readiness marker* instead of dead config. **No request is ever made.**
- Expected future response shape (documented in the module): `{"market", "crop", "value", "unit", "observed_at" (ISO-8601 with timezone), "source": {title, url, publisher, source_status, retrieved_at}, "provider": "amis"}`.
- Rules for any future implementation: only after a **verified stable API contract** (endpoint, auth, schema, terms) and PRD review; never HTML scraping; never a fabricated price; payloads must pass the same validation as farmer quotes. Until then payloads are recorded as not consumed.

## Safety rules (enforced, tested)

- **No price prediction** — outputs never contain prediction/forecast language (`UNSAFE_MARKET_TEXT` covers buy/sell/trading/profit/invest/prediction/forecast/guarantee/procurement/recommend/advice/speculation/…).
- **No trading, profit, yield, or procurement guidance** — price is information only.
- **Simulated data** is tagged `SIMULATED DEMO DATA` in the summary and `data`, never `complete`.
- **Stale quotes** carry `stale_badge`, the age, the freshness limit, and explicit "not presented as a current price" wording; never `is_official`.
- A price appears **only** from a validated farmer quote — never from the adapter, demo seed, or inference.

## Demo seed

`POST /api/v1/demo/seed` inserts **no** market quote (or weather/price/image fixture); its fixture string is tagged `SIMULATED INPUT SCENARIO (SIMULATED DEMO DATA)`.

## Sources

- Card-level: every quote card carries `Source(source_status="farmer_reported", publisher="Farmer")`.
- Registry: `farmer-market-quote` (farmer_reported, no URL) documents the source class; `amis` stays `unverified` with `url: null` — "Official current quotes are not enabled because a stable API contract was not verified". No sources are invented.

## Configuration

| Setting | Purpose |
|---|---|
| `MARKET_QUOTE_STALE_DAYS` (1–90, default 7) | freshness threshold for farmer quotes |
| `MARKET_ADAPTER_URL` | readiness marker for the future adapter (read by `adapter_status()`, never fetched) |

## Team package note (audit)

`agents/market/market/` arrived after the original "empty placeholder" state and is **not wired**: it is a provider-driven retriever (File/Sample/Null providers, bundled `data/sample_prices.json` mock prices, `MARKET_PRICE_FILE`/`MARKET_USE_SAMPLE` env, 3/14-day freshness, optional Groq `ai_enhance.py`). Wiring it would import bundled mock price paths and a third-party AI call — both out of scope; promote only after PRD review. The backend keeps farmer-quote-only behavior.

## Tests (`tests/test_market_agent.py`)

No quote → `unavailable` "Price unavailable" · valid quote → `complete` + `farmer_reported` source · missing unit → rejected · missing market → rejected · future date → rejected · old quote → `stale` + badge · adapter `None` → no fabricated price · adapter payload → not consumed · no unsafe trading/prediction language in any path · valid `AgentResult` envelope for every status · simulated quote tagged + never `complete` · demo seed tagged `SIMULATED DEMO DATA` · configurable stale threshold.

Run: `python -c "import app.main"`, `pytest -q`, or `pytest tests/test_market_agent.py -q`.

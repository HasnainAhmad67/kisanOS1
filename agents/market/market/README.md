# Market Agent  -  kisanos/agents/market/

Returns market-price EVIDENCE for a crop at a market: price, unit, date, source and whether the data is
available. Output is the team's MANDATORY 14-field JSON (identical to the Water Agent) plus the optional
AI_ENHANCED section. Information only: no buy / sell / hold advice, no price predictions, no chemicals.

## Flow (all 7 steps are built in; each one is a function in agent.py)
    MARKET AGENT
      1 Crop / produce                  step1_crop          wheat (MVP) - others -> unavailable
      2 Location / market               step2_location      "Bahawalpur", "Bahawalpur Mandi", "Multan, Punjab"
      3 Current available price data    step3_price_data    from a PROVIDER; the agent never invents prices
      4 Unit                            step4_unit          PKR per 40 kg | per kg | per 100 kg (+ PKR per kg)
      5 Date / freshness                step5_freshness     fresh <= 3 days, stale <= 14, older = too old
      6 Source                          step6_source        title, url, publisher, source_status, retrieved_at
      7 Data availability               step7_availability  available | partial | unavailable
              |
              v
      MARKET EVIDENCE                   build_market_evidence() -> evidence_to_contract() -> 14-field JSON
The 7 evidence lines are always the first 7 items of `observations`, in this order, labelled
"Crop / produce", "Location / market", "Current price data", "Unit", "Date / freshness", "Source",
"Data availability". Read them back with get_market_evidence(result).

## Files
    agent.py          the 7-step flow + MARKET EVIDENCE + 14-field JSON (analyze_market)
    schema.py         Pydantic models + validate_output() = the backend checks (same contract as Water Agent;
                      adds one guard: no trading advice / price predictions)
    providers.py      price-data providers + strict record validation (File, Sample, Null; plug in your own)
    ai_enhance.py     OPTIONAL AI_ENHANCED (Groq openai/gpt-oss-120b; Urdu / Roman Urdu / audio script)
    test_agent.py     22 tests (valid, unsupported, missing/invalid data, safety, providers, AI path)
    data/sample_prices.json         SAMPLE (mock) prices - always labelled, never presented as real
    data/real_prices_TEMPLATE.json  how to enter REAL prices (records is empty on purpose)
    requirements.txt  pydantic (required), groq + python-dotenv (optional)

## Run
    pip install -r requirements.txt
    python -c "from agent import analyze_market, DEMO_INPUT; print(analyze_market(**DEMO_INPUT))"   # SAMPLE data
    # from the kisanos/ folder:  from agents.market.agent import analyze_market

    result = analyze_market("wheat", "Bahawalpur")                       # real file if MARKET_PRICE_FILE is set
    result = analyze_market("wheat", "Bahawalpur", use_sample=True)      # demo: SAMPLE data, clearly labelled
    result = analyze_market("wheat", "Bahawalpur", provider=MyProvider())
    result = analyze_market("wheat", "Bahawalpur", enhance=True)         # + AI_ENHANCED

Inputs: crop, location (required); provider, use_sample, now (tests), enhance, use_llm, assessment_id (optional).

## Where prices come from (read this)
The agent has NO built-in live feed. A price is shown only if a provider supplies a valid record:
1. REAL prices: copy them from an official source into a JSON/CSV file (see data/real_prices_TEMPLATE.json),
   then set MARKET_PRICE_FILE=<path> in .env. Each record must have: crop, market, price, unit, price_date,
   source_title, source_url, publisher, source_status, retrieved_at (optional: district, price_min/max,
   provider="amis", currency PKR). Invalid records are skipped and reported, never shown.
2. SAMPLE prices: only when use_sample=True or MARKET_USE_SAMPLE=1. Output is always partial, band
   not_calibrated, flag sample_data_not_real, "SAMPLE (mock) ... NOT real mandi prices" in the summary and
   the price line, source_status unverified. Real file data always wins over sample data.
3. Nothing configured -> status unavailable (no price, no invented fallback).
4. Your own source (AMIS connector, database): any object with  fetch(crop, now) -> providers.ProviderResult.
AMIS_BASE_URL / DATABASE_URL from the team .env are NOT used here. See "Limits" about AMIS.

## How the mandatory fields are filled
- agent_id "market" | assessment_id uuid4 (or the one you pass) | version "1.0" | created_at UTC ISO-8601 with Z
- status: complete = real price, exact market, fresh, clear unit, source official/supporting |
  partial = sample data, stale price (4-14 days), same-district market instead of the requested one, or a
  secondary/unverified source | unavailable = unsupported crop, missing input, no data, unknown location,
  price older than 14 days, provider failure | error = invalid input type or internal error.
- evidence_band: high only for complete + official source; medium for complete + supporting source;
  low for partial; not_calibrated for sample data, unavailable and error.
- summary starts with "Market data availability: available | partial | unavailable."
- sources: the record used (title, url, publisher, retrieved_at, source_status); empty if no price was used.
- provider_or_model: "self-hosted", "amis" (record says provider=amis), or "groq" (Groq text actually used).
- safety_flags: sample_data_not_real | stale_price_data | different_market_used | unverified_source |
  unsupported_crop | unsupported_location | no_price_data | provider_error | records_skipped_invalid |
  invalid_input | ai_output_rejected | ai_enhancement_unavailable | unsafe_content_blocked | agent_internal_error
- AI_ENHANCED.priority_level: medium (available), low (partial / unavailable) - market info is informational.

## Safety
- Banned words (pesticide, spray, dose, fertilizer, urea ... also Urdu / Roman Urdu) and trading advice
  (sell now, buy now, will rise ... also Urdu / Roman Urdu) are checked on every string of the output; a failure
  returns status "error" with a safe message. Records whose text contains such words are rejected.
- Price sanity check: a price outside 20-500 PKR/kg for wheat is rejected (catches wrong-unit entries).
- The Groq model is used only for real, fresh, exact-market data; it must write NO digits; the price/unit/date
  sentence is built from the data. It never sees the price, place or date. Unsafe replies -> templates.
- The agent never raises; provider failures and bad input become a valid JSON.

## Test
    python test_agent.py                      (from this folder)
    python -m agents.market.test_agent        (from the kisanos/ folder)
All prices in the tests are made-up fixtures.

## .env (never push it to GitHub)
    MARKET_PRICE_FILE=path/to/real_prices.json   # real prices
    MARKET_USE_SAMPLE=1                          # optional: allow labelled SAMPLE data (demo only)
    GROQ_API_KEY=your_groq_key_here              # only for AI_ENHANCED with the real model
    MARKET_MODEL=openai/gpt-oss-120b             # optional, this is the default

## Limits
- No verified live data feed. When I tried to open amis.punjab.gov.pk and marketing.agripunjab.gov.pk, both
  refused automated access (robots), so no scraper is included. Ask the Punjab Agriculture Department for
  permission or an export before automating; the team .env points to amis.punjab.gov.pk while public pages link
  marketing.agripunjab.gov.pk - confirm which is correct.
- Freshness limits (3 / 14 days) and the 20-500 PKR/kg sanity range are tunable defaults, not from a source.
- Single price per market and day: no trend, forecast or history. Wheat only. Currency PKR only.
- The live Groq call was tested only with a fake client, not the real API.
- Urdu / Roman Urdu templates should be read by a native speaker before the demo.

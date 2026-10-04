"""Tests for the deterministic, fail-closed Market Agent.

Covers: unavailable without a quote, validated farmer quotes (complete +
farmer_reported source), rejection of missing unit/market, future timestamps
and invalid values, staleness with badge and configurable threshold, adapter
fail-closed behavior (None payload and ignored payload), unsafe-language
scans, AgentResult envelope validity, SIMULATED DEMO DATA tagging, and the
demo seed fixture tag.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agents import market as market_mod
from app.agents.market import UNSAFE_MARKET_TEXT, assess_market
from app.main import app
from app.schemas import AgentResult, FarmerMarketQuote

AID = str(uuid4())

# A price must never appear in a fail-closed ("Price unavailable") result.
PRICE_PATTERN = r"\d[\d,.]*\s*(?:PKR|Rs\b)"


def _quote(drop: tuple[str, ...] = (), **overrides) -> dict:
    quote = {
        "market": "Bahawalpur Sadar",
        "value": 4800.0,
        "unit": "PKR/100kg",
        "observed_at": (datetime.now(UTC) - timedelta(hours=3)).isoformat(),
    }
    quote.update(overrides)
    for key in drop:
        quote.pop(key, None)
    return quote


def _run(quote=None, intake_extra: dict | None = None) -> AgentResult:
    intake: dict = {"crop": "wheat", **(intake_extra or {})}
    if quote is not None:
        intake["market_quote"] = quote
    return assess_market(AID, intake)


def _text(result: AgentResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)


# ------------------------------------------------------------------ 1. no quote
def test_no_quote_is_unavailable_price_unavailable():
    for intake in ({}, {"market_quote": None}):
        result = assess_market(AID, intake)
        assert result.status == "unavailable"
        assert "Price unavailable" in result.summary
        assert result.data["quote"] is None
        assert result.sources == []
        assert "no_price_invented" in result.safety_flags
        assert "no price is inferred" in result.evidence_reason
        assert not re.search(PRICE_PATTERN, _text(result))
        AgentResult.model_validate(result.model_dump(mode="json"))


# ------------------------------------------------- 2. valid quote -> complete
def test_valid_farmer_quote_is_complete_and_farmer_reported():
    result = _run(_quote())
    assert result.status == "complete"
    assert result.agent_id == "market"
    assert result.provider_or_model == "farmer_reported"
    assert result.evidence_band == "low"
    assert "4800" in result.summary and "PKR/100kg" in result.summary
    assert "Bahawalpur Sadar" in result.summary

    assert len(result.sources) == 1
    source = result.sources[0]
    assert source.source_status == "farmer_reported"
    assert source.publisher == "Farmer"
    assert source.geography == "Bahawalpur Sadar"
    assert source.retrieved_at is not None

    assert result.data["quote"]["value"] == 4800.0
    assert result.data["freshness"] == "fresh"
    assert result.data["stale_badge"] is False
    assert result.data["is_official"] is False
    assert result.data["is_simulated"] is False
    assert "not verified against any official market feed" in result.summary
    assert "Farmer reported this quote" in result.observations[0]
    AgentResult.model_validate(result.model_dump(mode="json"))


# ----------------------------------------------------------- 3. missing unit
def test_missing_unit_is_rejected():
    result = _run(_quote(drop=("unit",)))
    assert result.status == "unavailable"
    assert "Price unavailable" in result.summary
    assert "unit_missing" in result.data["quote_problems"]
    assert "unit_missing" in result.safety_flags
    assert result.data["quote"] is None
    assert not re.search(PRICE_PATTERN, _text(result))


# -------------------------------------------------------- 4. missing market
def test_missing_market_is_rejected():
    for quote in (_quote(drop=("market",)), _quote(market=""), _quote(market="   ")):
        result = _run(quote)
        assert result.status == "unavailable", quote
        assert "market_name_missing" in result.data["quote_problems"]
        assert result.data["quote"] is None


# ---------------------------------------------------------- 5. future date
def test_future_observed_at_is_rejected():
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    result = _run(_quote(observed_at=future))
    assert result.status == "unavailable"
    assert "observed_at_future" in result.data["quote_problems"]
    assert "observed_at_future" in result.safety_flags
    assert result.data["quote"] is None
    assert not re.search(PRICE_PATTERN, _text(result))

    # Naive / missing timestamps are rejected too (fail-closed).
    naive = _run(_quote(observed_at="2026-10-01T09:00:00"))
    assert naive.status == "unavailable"
    assert "observed_at_timezone_missing" in naive.data["quote_problems"]
    missing = _run(_quote(drop=("observed_at",)))
    assert missing.status == "unavailable"
    assert "observed_at_missing" in missing.data["quote_problems"]
    assert not re.search(PRICE_PATTERN, _text(missing))


# ------------------------------------------------------------- 6. old quote
def test_old_quote_is_stale_with_badge():
    old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    result = _run(_quote(observed_at=old))
    assert result.status == "stale"
    assert result.data["stale_badge"] is True
    assert result.data["freshness"] == "stale"
    assert result.data["freshness_limit_days"] == 7
    assert result.data["age_days"] > 7
    assert result.data["is_official"] is False
    assert "stale_quote" in result.safety_flags
    assert "Stale quote" in result.summary
    assert "not presented as a current price" in result.summary
    assert "past the 7-day freshness limit" in result.evidence_reason
    # The stale quote still shows its value with provenance, not as current data.
    assert "4800" in result.summary
    assert result.sources[0].source_status == "farmer_reported"
    AgentResult.model_validate(result.model_dump(mode="json"))


# -------------------------------------------------- 7. adapter returns None
def test_adapter_none_yields_no_fabricated_price(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_fetch(market: str, crop: str):
        calls.append((market, crop))
        return None

    monkeypatch.setattr(market_mod, "fetch_market_quote", fake_fetch)
    monkeypatch.setattr(
        "app.services.market_adapter.get_settings",
        lambda: SimpleNamespace(market_adapter_url=None),
    )
    result = _run(None)
    assert calls and calls[0][1] == "wheat"
    assert result.status == "unavailable"
    assert result.data["quote"] is None
    assert result.data["adapter"]["reason"]
    assert result.data["adapter"]["configured"] is False
    assert "MARKET_ADAPTER_URL" in result.data["adapter"]["reason"]
    assert not re.search(PRICE_PATTERN, _text(result))


# -------------------------------------------- 7b. adapter payload not consumed
def test_adapter_payload_is_not_consumed_until_contract_verified(monkeypatch):
    def fake_fetch(market: str, crop: str):
        return {"market": market or "Bahawalpur", "crop": crop, "value": 9999.0, "unit": "PKR/100kg"}

    monkeypatch.setattr(market_mod, "fetch_market_quote", fake_fetch)
    result = _run(None)
    assert result.status == "unavailable"
    assert "adapter_payload_not_used" in result.safety_flags
    assert result.data["adapter"]["payload"] == "not_consumed_pending_contract_verification"
    assert "9999" not in _text(result)
    assert result.data["quote"] is None


# ------------------------------------------ 8. no unsafe trading/prediction text
def test_no_unsafe_trading_or_prediction_language():
    # The detector itself works on candidate language.
    for phrase in ("buy now", "price prediction", "sell your stock", "profit margin", "trading advice"):
        assert UNSAFE_MARKET_TEXT.search(phrase), phrase

    old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    results = [
        _run(None),
        _run(_quote()),
        _run(_quote(observed_at=old)),
        _run(_quote(simulated=True)),
        _run(_quote(drop=("unit",))),
        _run(_quote(value=-5)),
    ]
    for result in results:
        assert not UNSAFE_MARKET_TEXT.search(_text(result)), _text(result)
        assert result.possible_causes == []
        assert len(result.checks) <= 8


# ------------------------------------------------- 9. valid AgentResult envelope
def test_valid_agentresult_envelope_for_every_status():
    old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    for quote in (None, _quote(), _quote(observed_at=old), _quote(simulated=True), _quote(value=0)):
        result = _run(quote)
        validated = AgentResult.model_validate(result.model_dump(mode="json"))
        assert validated.agent_id == "market"
        assert validated.status in {"complete", "stale", "partial", "unavailable"}
        assert validated.version == "market-safe-adapter-1.1.0"
        assert validated.evidence_reason
        assert validated.provider_or_model


# ---------------------------------------------- 10. demo seed tagged SIMULATED
def test_demo_seed_is_tagged_simulated_demo_data():
    with TestClient(app) as client:
        response = client.post("/api/v1/demo/seed")
        assert response.status_code == 201
        fixture = response.json()["demo_fixture"]
        assert "SIMULATED DEMO DATA" in fixture
        assert "SIMULATED INPUT SCENARIO" in fixture
        assert "no simulated weather" in fixture
        assert "market price" in fixture  # the fixture states no price is inserted

# ------------------------------------- 10b. simulated quote tagged, never complete
def test_simulated_quote_is_tagged_and_never_complete():
    # Intake schema accepts the explicit marker (default False).
    parsed = FarmerMarketQuote(
        market="Bahawalpur Sadar",
        value=4800.0,
        unit="PKR/100kg",
        observed_at=datetime.now(UTC) - timedelta(hours=1),
        simulated=True,
    )
    assert parsed.simulated is True
    assert FarmerMarketQuote(
        market="Bahawalpur Sadar",
        value=4800.0,
        unit="PKR/100kg",
        observed_at=datetime.now(UTC) - timedelta(hours=1),
    ).simulated is False

    result = _run(_quote(simulated=True))
    assert result.status == "partial"
    assert "SIMULATED DEMO DATA" in result.summary
    assert result.data["data_classification"] == "SIMULATED DEMO DATA"
    assert result.data["is_simulated"] is True
    assert "simulated_demo_data" in result.safety_flags
    assert "not a live price" in result.summary
    AgentResult.model_validate(result.model_dump(mode="json"))


# ------------------------------------------- extra: configurable stale threshold
def test_stale_threshold_is_configurable(monkeypatch):
    monkeypatch.setattr(
        market_mod, "get_settings", lambda: SimpleNamespace(market_quote_stale_days=3)
    )
    freshish = _run(_quote(observed_at=(datetime.now(UTC) - timedelta(days=2)).isoformat()))
    assert freshish.status == "complete"
    assert freshish.data["freshness_limit_days"] == 3

    older = _run(_quote(observed_at=(datetime.now(UTC) - timedelta(days=5)).isoformat()))
    assert older.status == "stale"
    assert older.data["freshness_limit_days"] == 3


# ------------------------------------------------ extra: invalid value handling
def test_invalid_values_are_rejected():
    for value, problem in [(-5, "value_not_positive"), (0, "value_not_positive"), ("abc", "value_not_a_number")]:
        result = _run(_quote(value=value))
        assert result.status == "unavailable", value
        assert problem in result.data["quote_problems"], value

    result = _run("not-a-quote-object")
    assert result.status == "unavailable"
    assert "quote_not_an_object" in result.data["quote_problems"]

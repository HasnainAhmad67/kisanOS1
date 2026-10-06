"""Focused tests for the official Punjab AMIS wheat price reader.

Covers: successful Bahawalpur wheat parsing (market, unit, prices, date, source
URL), wrong commodity / absent market (fail closed, never another city),
timeout and invalid HTML (no exception escapes), freshness (fresh / stale /
unknown, an old quote is never labelled current), future source dates, cache
TTL behaviour, the HTTP client contract, pilot-area mapping, and the fallback
to the farmer-entered quote when AMIS is unreachable.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.agents import market as market_mod
from app.agents.market import AMIS_NOT_AVAILABLE_OBSERVED, NO_QUOTE_REASON, assess_market
from app.schemas import AgentResult
from app.team_agents.market import amis as amis_mod

# Captured at import time (before any fixture can install the no-network guard).
_REAL_FETCH_HTML = amis_mod.fetch_html

AID = str(uuid4())
URL = "http://www.amis.pk/ViewPrices.aspx?searchType=0&commodityId=1"
# A price must never appear in a fail-closed ("Price unavailable") result.
PRICE_PATTERN = r"\d[\d,.]*\s*(?:PKR|Rs\b)"


# ------------------------------------------------------------------ fixtures
class _Settings:
    def __init__(self, enabled=True, url=URL, timeout=8.0, ttl=900):
        self.amis_enabled = enabled
        self.amis_wheat_url = url
        self.amis_timeout_sec = timeout
        self.amis_cache_ttl_sec = ttl


@pytest.fixture(autouse=True)
def _clean_cache():
    amis_mod.clear_cache()
    yield
    amis_mod.clear_cache()


def _enable(monkeypatch, **kwargs) -> _Settings:
    settings = _Settings(**kwargs)
    monkeypatch.setattr(amis_mod, "get_settings", lambda: settings)
    return settings


def _cell(text: str) -> str:
    return f'<td style="border-right: 1px solid black;">&nbsp;{text}</td>'


def _row(index: int, city: str, prices: tuple[str, str, str], city_id: int) -> str:
    return (
        '<tr style="font-family:verdana;">'
        f'<td>&nbsp;<b>{index}&nbsp<a href="http://www.amis.pk/ViewPrices.aspx?'
        f'searchType=1&commodityId={city_id}">{city}</a></b></td>'
        + _cell("Graph")
        + _cell(prices[0])
        + _cell(prices[1])
        + _cell(prices[2])
        + _cell("-")
        + "</tr>"
    )


def _page(
    *,
    commodity: str = "Wheat",
    dated: str | None = "05-10-2026",
    unit: str = "Rs/100Kg",
    bahawalpur: tuple[str, str, str] | None = ("9500", "9600", "9550"),
    extra_markets: dict[str, tuple[str, str, str]] | None = None,
    third_column_header: str = "FQP",
) -> str:
    """Deterministic stand-in for the AMIS page (same structure as production)."""
    markets: dict[str, tuple[str, str, str]] = dict(extra_markets or {})
    if bahawalpur is not None:
        markets.setdefault("BahawalPur", bahawalpur)
    markets.setdefault("Multan", ("11400", "11600", "11500"))
    markets.setdefault("Lahore", ("-", "-", "-"))

    header = (
        "<tr style=\"background-color:#FFFFE0;\">"
        + _cell(f"Dated:{dated}" if dated else "Date")
        + _cell("Graph")
        + _cell("Min")
        + _cell("Max")
        + _cell(third_column_header)
        + _cell("Quantity")
        + "</tr>"
    )
    rows = "".join(
        _row(index, city, prices, index)
        for index, (city, prices) in enumerate(markets.items(), start=1)
    )
    return (
        "<!DOCTYPE html><html><body>"
        '<div id="selectedcommodity"><H2>Commodity:  <B>'
        f'<span id="ctl00_cphPage_lblMsg">{commodity}</span> '
        '<span id="ctl00_cphPage_lblquintal"><font color="Red" size="1">'
        f"[ All Prices are in {unit} specified otherwise ]"
        "</font></span></B></H2></div>"
        f"<table>{header}{rows}</table>"
        "</body></html>"
    )


def _fetch_pages(*pages: str):
    """fetch_html stand-in returning each page in turn (last one repeats)."""
    calls: list[str] = []

    def fake_fetch(url: str, timeout: float) -> str:
        calls.append(url)
        return pages[min(len(calls) - 1, len(pages) - 1)]

    fake_fetch.calls = calls  # type: ignore[attr-defined]
    return fake_fetch


def _fetch_error(exc: Exception):
    def fake_fetch(url: str, timeout: float) -> str:
        raise exc

    return fake_fetch


def _today(offset_days: int = 0) -> str:
    day = datetime.now(amis_mod.SOURCE_TZ) + timedelta(days=offset_days)
    return day.strftime("%d-%m-%Y")


def _today_iso(offset_days: int = 0) -> str:
    day = datetime.now(amis_mod.SOURCE_TZ) + timedelta(days=offset_days)
    return day.date().isoformat()


def _text(result: AgentResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)


def _run(intake: dict | None = None) -> AgentResult:
    return assess_market(AID, {"crop": "wheat", **(intake or {})})


# ------------------------------------------------------------------ 1. disabled
def test_disabled_by_default_never_fetches(monkeypatch):
    _enable(monkeypatch, enabled=False)

    def boom(url: str, timeout: float) -> str:  # pragma: no cover - must not run
        raise AssertionError("AMIS must not be fetched while disabled")

    monkeypatch.setattr(amis_mod, "fetch_html", boom)

    quote, diag = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is None
    assert diag["enabled"] is False
    assert diag["attempted"] is False
    assert diag["reason"] == "amis_disabled"

    result = _run()
    assert result.status == "unavailable"
    assert NO_QUOTE_REASON in result.summary
    assert result.data["amis"]["reason"] == "amis_disabled"
    assert not re.search(PRICE_PATTERN, _text(result))


# --------------------------------------------------------- 2. successful quote
def test_bahawalpur_wheat_quote_is_parsed_and_shown(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(amis_mod, "fetch_html", _fetch_pages(_page(dated=_today())))

    quote, diag = amis_mod.fetch_quote("Bahawalpur Sadar", "wheat")
    assert diag["reason"] == ""
    assert quote is not None
    assert quote["source"] == "AMIS"
    assert quote["source_url"] == URL
    assert quote["market"] == "Bahawalpur"
    assert quote["market_reported_by_source"] == "BahawalPur"
    assert quote["commodity"] == "Wheat"
    assert quote["currency"] == "PKR"
    assert quote["unit"] == "Rs/100Kg"
    assert quote["min_price"] == 9500.0
    assert quote["max_price"] == 9600.0
    assert quote["average_price"] is None  # "FQP" is not a labelled average
    assert quote["source_date"] == _today_iso()
    assert str(quote["quoted_at"]).startswith(_today_iso())
    assert quote["retrieved_at"]
    assert quote["verification_status"] == "source_reported"
    assert quote["freshness"] == "fresh"
    assert quote["evidence_band"] == "medium"

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "complete"
    assert result.evidence_band == "medium"
    assert result.provider_or_model == "amis_source_reported"
    assert "AMIS wheat price" in result.summary
    assert "Bahawalpur" in result.summary
    assert "9500" in result.summary and "9600" in result.summary
    assert "Rs/100Kg" in result.summary
    assert _today_iso() in result.summary
    assert "freshness fresh" in result.summary

    source = result.sources[0]
    assert source.url == URL
    assert source.source_status == "official"
    assert source.publisher.startswith("Punjab Agriculture Marketing Information Service")
    assert source.geography == "Bahawalpur"
    assert source.retrieved_at is not None

    assert result.data["quote"]["min_price"] == 9500.0
    assert result.data["freshness"] == "fresh"
    assert result.data["verification_status"] == "source_reported"
    assert result.data["is_official"] is True
    assert result.data["is_simulated"] is False
    assert "amis_source_reported" in result.safety_flags
    AgentResult.model_validate(result.model_dump(mode="json"))


# --------------------------------------------------- 3. average only if labelled
def test_average_is_parsed_only_when_clearly_labelled(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        amis_mod,
        "fetch_html",
        _fetch_pages(_page(dated=_today(), third_column_header="Average")),
    )
    quote, _ = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is not None and quote["average_price"] == 9550.0

    monkeypatch.setattr(
        amis_mod, "fetch_html", _fetch_pages(_page(dated=_today(), third_column_header="FQP"))
    )
    amis_mod.clear_cache()
    quote, _ = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is not None and quote["average_price"] is None


# ------------------------------------------------------- 4. wrong commodity
def test_wrong_commodity_fails_closed(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        amis_mod, "fetch_html", _fetch_pages(_page(commodity="Rice", dated=_today()))
    )

    quote, diag = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is None
    assert diag["reason"] == "amis_commodity_mismatch"

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "unavailable"
    assert result.data["quote"] is None
    assert not re.search(PRICE_PATTERN, _text(result))


# -------------------------------------------------- 5. market absent -> no city swap
def test_missing_market_never_substitutes_another_city(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        amis_mod, "fetch_html", _fetch_pages(_page(bahawalpur=None, dated=_today()))
    )

    quote, diag = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is None
    assert diag["reason"] == "amis_market_not_returned"

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "unavailable"
    assert (
        "No verified Bahawalpur wheat quote was returned by AMIS today."
        in result.summary
    )
    assert "Multan" not in _text(result) and "Lahore" not in _text(result)
    assert "11400" not in _text(result)
    assert "no_price_invented" in result.safety_flags
    assert "amis_unavailable" in result.safety_flags
    assert not re.search(PRICE_PATTERN, _text(result))


# ---------------------------------------------------------------- 6. timeouts
def test_timeout_is_safe_unavailable(monkeypatch):
    _enable(monkeypatch, timeout=0.1)
    monkeypatch.setattr(
        amis_mod, "fetch_html", _fetch_error(httpx.TimeoutException("timed out"))
    )

    quote, diag = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is None
    assert diag["reason"].startswith("amis_fetch_failed:")

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "unavailable"
    assert "Price unavailable" in result.summary
    assert "no price is inferred" in result.evidence_reason
    assert not re.search(PRICE_PATTERN, _text(result))
    AgentResult.model_validate(result.model_dump(mode="json"))


# ------------------------------------------------------------ 7. invalid HTML
def test_invalid_html_is_safe_unavailable(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        amis_mod,
        "fetch_html",
        _fetch_pages("<html><body><p>Service unavailable - please retry</p></body></html>"),
    )

    quote, diag = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is None
    assert diag["reason"] in {
        "amis_price_table_not_found",
        "amis_commodity_label_missing",
    }

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "unavailable"
    assert not re.search(PRICE_PATTERN, _text(result))


# ------------------------------------------------------------- 8. stale quote
def test_old_source_date_is_stale_and_never_current(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        amis_mod, "fetch_html", _fetch_pages(_page(dated=_today(-5)))
    )

    quote, diag = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is not None
    assert quote["freshness"] == "stale"
    assert quote["evidence_band"] == "low"
    assert diag["reason"] == ""

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "stale"
    assert "freshness stale" in result.summary
    assert "freshness fresh" not in result.summary
    assert "not presented as a current price" in result.summary
    assert result.data["stale_badge"] is True
    assert result.data["freshness"] == "stale"
    assert "stale_quote" in result.safety_flags
    # The quote is still shown with its provenance, just never as today's price.
    assert "9500" in result.summary
    AgentResult.model_validate(result.model_dump(mode="json"))


# ----------------------------------------------------- 9. no source date -> unknown
def test_missing_source_date_is_unknown_not_current_day(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(amis_mod, "fetch_html", _fetch_pages(_page(dated=None)))

    quote, _ = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is not None
    assert quote["freshness"] == "unknown"
    assert quote["source_date"] is None
    assert quote["quoted_at"] is None

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "partial"
    assert "source date unavailable" in result.summary
    assert "freshness date unavailable" in result.summary
    assert "freshness fresh" not in result.summary
    assert "freshness stale" not in result.summary
    assert "source_date_missing" in result.safety_flags
    AgentResult.model_validate(result.model_dump(mode="json"))


# ------------------------------------------------------- 10. future source date
def test_future_source_date_fails_closed(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        amis_mod, "fetch_html", _fetch_pages(_page(dated=_today(+3)))
    )

    quote, diag = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert quote is None
    assert diag["reason"] == "amis_source_date_in_future"

    result = _run({"area_code": "bahawalpur_sadar"})
    assert result.status == "unavailable"
    assert not re.search(PRICE_PATTERN, _text(result))


# ------------------------------------------------------------------- 11. cache
def test_cache_is_best_effort_and_never_survives_its_ttl(monkeypatch):
    _enable(monkeypatch, ttl=900)
    fetch = _fetch_pages(_page(dated=_today()))
    monkeypatch.setattr(amis_mod, "fetch_html", fetch)

    first, diag1 = amis_mod.fetch_quote("Bahawalpur", "wheat")
    second, diag2 = amis_mod.fetch_quote("Bahawalpur Sadar", "wheat")
    assert first is not None and second is not None
    assert diag1["cache"] == "miss" and diag2["cache"] == "hit"
    assert len(fetch.calls) == 1  # cache key = market + commodity

    # A different market is a different key -> a separate lookup (and, since
    # this page has no Ahmadpur East row, a fail-closed answer).
    third, diag3 = amis_mod.fetch_quote("Ahmadpur East", "wheat")
    assert third is None
    assert diag3["reason"] == "amis_market_not_returned"
    assert diag3["cache"] == "miss"
    assert len(fetch.calls) == 2

    # Expire the entry: the next call must go back to the source.
    key = ("bahawalpur", "wheat")
    with amis_mod._CACHE_LOCK:
        stored_at, quote = amis_mod._CACHE[key]
        amis_mod._CACHE[key] = (stored_at - 901, quote)
    _, diag4 = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert diag4["cache"] == "miss" and diag4["attempted"] is True
    assert len(fetch.calls) == 3

    # Expired entry + failing fetch -> no quote at all (never a stale cache hit).
    monkeypatch.setattr(amis_mod, "fetch_html", _fetch_error(httpx.ConnectError("nope")))
    with amis_mod._CACHE_LOCK:
        stored_at, quote = amis_mod._CACHE[key]
        amis_mod._CACHE[key] = (stored_at - 901, quote)
    expired, diag5 = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert expired is None
    assert diag5["reason"].startswith("amis_fetch_failed:")

    # TTL = 0 disables caching entirely: every call goes back to the source.
    _enable(monkeypatch, ttl=0)
    counter = _fetch_pages(_page(dated=_today()))
    monkeypatch.setattr(amis_mod, "fetch_html", counter)
    _, diag6 = amis_mod.fetch_quote("Bahawalpur", "wheat")
    _, diag7 = amis_mod.fetch_quote("Bahawalpur", "wheat")
    assert diag6["cache"] == "miss" and diag7["cache"] == "miss"
    assert len(counter.calls) == 2


# --------------------------------------------------------- 12. HTTP contract
def test_fetch_html_uses_timeout_and_normal_user_agent(monkeypatch):
    seen: dict = {}

    class _Response:
        encoding = "utf-8"
        content = b"<html></html>"

        def raise_for_status(self) -> None:
            seen["status"] = 200

    class _Client:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url: str):
            seen["url"] = url
            return _Response()

    monkeypatch.setattr(amis_mod.httpx, "Client", _Client)
    html = _REAL_FETCH_HTML(URL, 8.0)

    assert html == "<html></html>"
    assert seen["url"] == URL
    assert seen["timeout"] == 8.0
    assert seen["follow_redirects"] is True
    agent = seen["headers"]["User-Agent"]
    assert agent.startswith("KisanOS-MarketAgent/1.0")
    assert "Mozilla" not in agent and "HeadlessChrome" not in agent


# ---------------------------------------------------------- 13. pilot areas
def test_pilot_area_mapping_fails_closed_when_absent(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(amis_mod, "fetch_html", _fetch_pages(_page(dated=_today())))

    # Yazman has no AMIS market on the page -> fail closed, no city swap.
    quote, diag = amis_mod.fetch_quote("Yazman", "wheat")
    assert quote is None
    assert diag["reason"] == "amis_market_not_returned"

    result = _run({"area_code": "yazman"})
    assert result.status == "unavailable"
    assert "No verified Yazman wheat quote was returned by AMIS today." in result.summary
    assert "Bahawalpur" not in result.summary


def test_pilot_area_with_exact_amis_market_is_used(monkeypatch):
    _enable(monkeypatch)
    page = _page(
        dated=_today(),
        bahawalpur=None,
        extra_markets={"AhmadPurEast": ("9300", "9450", "9375")},
    )
    monkeypatch.setattr(amis_mod, "fetch_html", _fetch_pages(page))

    quote, _ = amis_mod.fetch_quote("Ahmadpur East", "wheat")
    assert quote is not None
    assert quote["market"] == "Ahmadpur East"
    assert quote["market_reported_by_source"] == "AhmadPurEast"
    assert quote["min_price"] == 9300.0


def test_market_row_without_prices_fails_closed(monkeypatch):
    _enable(monkeypatch)
    page = _page(
        dated=_today(),
        bahawalpur=None,
        extra_markets={"AhmadPurEast": ("-", "-", "-")},
    )
    monkeypatch.setattr(amis_mod, "fetch_html", _fetch_pages(page))

    quote, diag = amis_mod.fetch_quote("Ahmadpur East", "wheat")
    assert quote is None
    assert diag["reason"] == "amis_row_has_no_prices"

    result = _run({"area_code": "ahmadpur_east"})
    assert result.status == "unavailable"
    assert (
        "No verified Ahmadpur East wheat quote was returned by AMIS today."
        in result.summary
    )
    assert not re.search(PRICE_PATTERN, _text(result))


def test_bahawalpur_sadar_and_city_both_query_bahawalpur(monkeypatch):
    for requested in ("Bahawalpur Sadar", "Bahawalpur City", "Bahawalpur"):
        assert amis_mod.market_target(requested) == "Bahawalpur"
    assert amis_mod.requested_market({"area_code": "bahawalpur_sadar"}) == "Bahawalpur Sadar"
    assert amis_mod.requested_market({"area_code": "yazman"}) == "Yazman"
    assert (
        amis_mod.requested_market({"market_quote": {"market": "Hasilpur"}}) == "Hasilpur"
    )
    assert amis_mod.requested_market({}) == ""


# ------------------------------------- 14. farmer quote fallback when AMIS fails
def test_farmer_quote_is_used_when_amis_is_unreachable(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(amis_mod, "fetch_html", _fetch_error(httpx.ConnectTimeout("slow")))

    observed = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    result = _run(
        {
            "area_code": "bahawalpur_sadar",
            "market_quote": {
                "market": "Bahawalpur Sadar",
                "value": 4800.0,
                "unit": "PKR/100kg",
                "observed_at": observed,
            },
        }
    )
    assert result.status == "complete"
    assert result.provider_or_model == "farmer_reported"
    assert result.data["quote"]["value"] == 4800.0
    assert result.data["amis"]["reason"].startswith("amis_fetch_failed:")
    assert AMIS_NOT_AVAILABLE_OBSERVED in result.observations


# ------------------------------------------------------- 15. no unsafe language
def test_amis_results_contain_no_advice_or_prediction_language(monkeypatch):
    _enable(monkeypatch)
    dated = _today()
    for page in (_page(dated=dated), _page(dated=_today(-5)), _page(dated=None)):
        monkeypatch.setattr(amis_mod, "fetch_html", _fetch_pages(page))
        amis_mod.clear_cache()
        result = _run({"area_code": "bahawalpur_sadar"})
        assert not market_mod.UNSAFE_MARKET_TEXT.search(_text(result)), _text(result)
        assert result.possible_causes == []
        assert len(result.checks) <= 8


# --------------------------------------------------------- 16. live page shape
def test_live_amis_markup_shape_is_understood():
    """Parser self-check against the published AMIS markup structure."""
    html = _page(dated="05-10-2026")
    rows = amis_mod.extract_rows(html)
    assert any(amis_mod._header_columns(row) for row in rows)
    assert amis_mod.unit_label(html) == "Rs/100Kg"
    assert amis_mod.commodity_label(html) == "Wheat"
    assert amis_mod.parse_source_date("Dated:05-10-2026").isoformat() == "2026-10-05"
    assert amis_mod.parse_source_date("Dated:") is None
    assert amis_mod.parse_source_date("Date") is None

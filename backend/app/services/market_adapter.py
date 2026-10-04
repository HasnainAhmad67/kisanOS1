"""Plug-in contract for a future verified market-price data source (AMIS).

STATUS: the PRD records that AMIS has **no verified stable API contract**, so
no fetching, scraping, or API client exists here. ``fetch_market_quote()``
always returns ``None`` today, ``adapter_status()`` explains why, and the
Market Agent stays fail-closed ("Price unavailable") whenever no
farmer-entered quote exists. Never scrape HTML: a future implementation may
only run after an API contract (endpoint, auth, response schema, terms) is
verified and approved, and after PRD review.

Configuration:
    MARKET_ADAPTER_URL (settings.market_adapter_url) is a **readiness
    marker only** while nothing is implemented: adapter_status() reports it
    so the setting is no longer dead config, but no request is ever made.

Contract for the future implementation::

    fetch_market_quote(market: str, crop: str) -> dict | None

    Returns the quote below, or ``None`` (reason in ``adapter_status()``)
    when no adapter is configured. Expected response shape - the future
    AMIS implementation must return exactly this dict shape::

        {
          "market": "Bahawalpur",              # market / mandi name
          "crop": "wheat",
          "value": 4800.0,                     # number, > 0
          "unit": "PKR/100kg",                 # explicit unit, never implied
          "observed_at": "2026-10-04T09:00:00+05:00",   # ISO-8601 with timezone
          "source": {
            "title": "<page or report name>",
            "url": "https://<exact page>",
            "publisher": "<who publishes it>",
            "source_status": "official|supporting|secondary|unverified",
            "retrieved_at": "2026-10-04T09:00:00Z"
          },
          "provider": "amis"
        }

Even when such a payload exists, the Market Agent does NOT display it until
the contract is verified (the payload is recorded as not consumed). Prices
are information only: no prediction, no trading/profit/procurement guidance.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings

NOT_CONFIGURED_REASON = (
    "market adapter not configured; set MARKET_ADAPTER_URL only after an AMIS "
    "API contract has been verified and approved"
)
CONTRACT_PENDING_REASON = (
    "MARKET_ADAPTER_URL is set but fetching is not implemented: the AMIS API "
    "contract is still unverified (PRD: no stable contract was verified)"
)


def adapter_status() -> dict[str, Any]:
    """Readiness of the future adapter (this also keeps MARKET_ADAPTER_URL live)."""
    configured = bool(get_settings().market_adapter_url)
    return {
        "configured": configured,
        "reason": CONTRACT_PENDING_REASON if configured else NOT_CONFIGURED_REASON,
    }


def fetch_market_quote(market: str, crop: str) -> dict | None:
    """Return a verified-contract market quote, or None when unavailable.

    Nothing is fetched today: with no verified AMIS API contract this always
    returns ``None``; the reason is reported by ``adapter_status()``. The
    future implementation must honor the response shape in the module
    docstring, must never scrape HTML, and must never invent a price.
    """
    return None

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.schemas import AgentResult, Source
from app.services.market_adapter import adapter_status, fetch_market_quote
from app.team_agents.market.amis import (
    PUBLISHER as AMIS_PUBLISHER,
    SOURCE_TITLE as AMIS_SOURCE_TITLE,
    fetch_quote as fetch_amis_quote,
    requested_market as amis_requested_market,
)

VERSION = "market-safe-adapter-1.1.0"

# Language the Market Agent must never emit: no price predictions, no
# trading/profit/yield guidance, no procurement advice.
UNSAFE_MARKET_TEXT = re.compile(
    r"\b(buy|sell|trading|trade|profit\w*|invest\w*|prediction|predict\w*|"
    r"forecast\w*|guarantee\w*|procurement|procure\w*|recommend\w*|advis\w*|"
    r"speculat\w*|tender|bid|earning\w*|yield)\b",
    re.IGNORECASE,
)

NO_QUOTE_REASON = (
    "no verified current AMIS quote or farmer-entered quote was supplied."
)

# Static English sentences for the official AMIS path. They are mapped to Urdu
# in frontend/src/i18n/backendText.ts, so keep them byte-stable.
AMIS_OBSERVED = (
    "Retrieved from Punjab AMIS; KisanOS did not edit, estimate, or infer any price."
)
AMIS_REASON_FRESH = (
    "Source-reported quote from Punjab AMIS; freshness is derived from the AMIS "
    "source date and KisanOS did not alter, estimate, or infer any price."
)
AMIS_REASON_STALE = (
    "Punjab AMIS source date is older than 24 hours; the quote is shown as stale "
    "and is not presented as current."
)
AMIS_REASON_UNKNOWN_DATE = (
    "Punjab AMIS returned no source date; the quote is shown as source-reported "
    "with the date unavailable, not as today's price."
)
AMIS_CHECK_CONFIRM = (
    "Confirm the unit and grade with the mandi before you compare this quote "
    "with another rate."
)
AMIS_CHECK_FRESHNESS = (
    "Ask your local market committee or arhti for today's rate before relying on "
    "this number."
)
AMIS_STALE_OBSERVED = (
    "The AMIS source date is older than 24 hours, so this quote is not labelled "
    "as current."
)
AMIS_NO_DATE_OBSERVED = "AMIS returned no source date for this quote."
AMIS_NOT_AVAILABLE_OBSERVED = (
    "Punjab AMIS did not return a usable quote today, so only the farmer-entered "
    "quote is shown."
)
NO_AMIS_DIAG = {
    "enabled": False,
    "attempted": False,
    "reason": "not_attempted",
    "url": "",
    "cache": "bypass",
    "market": "",
    "rows_seen": 0,
}


def _no_quote_reason(amis: dict[str, Any]) -> str:
    """Why there is no price, for the AMIS-enabled path (fail-closed)."""
    if not amis.get("enabled"):
        return NO_QUOTE_REASON
    reason = str(amis.get("reason") or "")
    market = str(amis.get("market") or "Bahawalpur")
    if reason in {"amis_market_not_returned", "amis_row_has_no_prices"}:
        # Required wording: never name a different city than the one requested.
        return f"No verified {market} wheat quote was returned by AMIS today."
    if reason.startswith("amis_fetch_failed"):
        return (
            "the official AMIS price page could not be reached, so no verified "
            "quote is available today."
        )
    if reason in {"amis_disabled", ""}:
        return NO_QUOTE_REASON
    return "AMIS did not return a usable wheat quote today."


def _parse_observed(value: Any, now: datetime) -> tuple[datetime | None, str | None]:
    """ISO-8601 string or datetime -> aware UTC datetime, or (None, problem)."""
    if value is None:
        return None, "observed_at_missing"
    if isinstance(value, datetime):
        observed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            observed = datetime.fromisoformat(text)
        except ValueError:
            return None, "observed_at_invalid"
    else:
        return None, "observed_at_invalid"
    if observed.tzinfo is None:
        return None, "observed_at_timezone_missing"
    observed = observed.astimezone(UTC)
    if observed > now:
        return None, "observed_at_future"
    return observed, None


def _validate_quote(quote: Any, now: datetime) -> tuple[dict[str, Any] | None, list[str]]:
    """B1-B4 validation: positive numeric value, unit present, market present,
    observation time present with a timezone and never in the future."""
    if not isinstance(quote, dict):
        return None, ["quote_not_an_object"]
    problems: list[str] = []

    market = quote.get("market")
    if isinstance(market, str) and market.strip():
        market = market.strip()[:100]
    else:
        market = None
        problems.append("market_name_missing")

    raw = quote.get("value")
    value: float | None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        value = None
        problems.append("value_not_a_number")
    else:
        value = float(raw)
        if not math.isfinite(value):
            value = None
            problems.append("value_not_a_number")
        elif value <= 0:
            value = None
            problems.append("value_not_positive")
        elif value > 1_000_000:
            value = None
            problems.append("value_out_of_range")

    unit = quote.get("unit")
    if isinstance(unit, str) and unit.strip():
        unit = unit.strip()[:40]
    else:
        unit = None
        problems.append("unit_missing")

    observed, observed_problem = _parse_observed(quote.get("observed_at"), now)
    if observed_problem:
        problems.append(observed_problem)

    if problems:
        return None, problems
    return {
        "market": market,
        "value": value,
        "unit": unit,
        "observed_at": observed,
        "simulated": bool(quote.get("simulated", False)),
    }, []


def _probe_adapter(
    intake: dict[str, Any], market: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Consult the future AMIS adapter when a price would have been needed.

    Nothing is fetched today (no verified contract). Any payload is recorded
    but never consumed - fail-closed until the AMIS API contract is verified.
    """
    status = adapter_status()
    payload = fetch_market_quote(market=market, crop=str(intake.get("crop") or "wheat"))
    if payload is not None:
        status = {**status, "payload": "not_consumed_pending_contract_verification"}
    return payload, status


def _unavailable_result(
    assessment_id: str,
    now: datetime,
    reason: str,
    problems: list[str],
    adapter: dict[str, Any],
    payload_seen: bool,
    input_evidence: list[str],
    extra_flags: list[str] | None = None,
    amis: dict[str, Any] | None = None,
) -> AgentResult:
    flags = ["no_price_invented", *problems, *(extra_flags or [])]
    if payload_seen:
        flags.append("adapter_payload_not_used")
    evidence_reason = (
        "No market quote was retrieved or provided; no price is inferred."
        if not problems
        else "The supplied quote failed validation ("
        + ", ".join(problems)
        + "); no price is shown."
    )
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="market",
        status="unavailable",
        summary=f"Price unavailable: {reason}",
        observations=[],
        possible_causes=[],
        checks=[
            "Enter a recent market quote, or ask your local market committee for the current rate."
        ],
        evidence_band="not_calibrated",
        evidence_reason=evidence_reason,
        sources=[],
        provider_or_model=(
            "AMIS adapter not configured; fail-closed"
            if not adapter.get("configured")
            else "AMIS adapter contract unverified; fail-closed"
        ),
        version=VERSION,
        created_at=now,
        safety_flags=flags,
        data={
            "quote": None,
            "freshness": "unavailable",
            "quote_problems": list(problems),
            "adapter": adapter,
            "amis": dict(amis) if amis is not None else dict(NO_AMIS_DIAG),
        },
        input_evidence=input_evidence,
    )


def _quote_result(
    assessment_id: str,
    quote: dict[str, Any],
    now: datetime,
    stale_days: int,
    adapter: dict[str, Any],
    amis: dict[str, Any] | None = None,
) -> AgentResult:
    observed: datetime = quote["observed_at"]
    age_hours = (now - observed).total_seconds() / 3600
    age_days = age_hours / 24
    stale = age_days > stale_days
    simulated = quote["simulated"]
    market, value, unit = quote["market"], quote["value"], quote["unit"]
    observed_text = observed.isoformat()

    if stale:
        # D5: stale quotes carry an explicit badge and are never presented as current.
        status, band = "stale", "low"
        tag = "SIMULATED DEMO DATA - not a live price. " if simulated else ""
        summary = (
            f"{tag}Stale quote: farmer-reported {value:g} {unit} for {market}, observed "
            f"{age_days:.0f} day(s) ago (freshness limit {stale_days} days); "
            "not presented as a current price."
        )
        evidence_reason = (
            f"Farmer-entered quote is {age_days:.0f} days old, past the {stale_days}-day "
            "freshness limit; provenance is farmer_reported and not independently verified."
        )
        flags = ["stale_quote", "not_official_market_data", "farmer_reported_only"]
        checks = [
            "Ask your local market committee or arhti for today's rate before relying on this number.",
            "Confirm the unit and grade with the person who reported the quote.",
        ]
    elif simulated:
        # A4/D4: simulated data is always tagged and never presented as live.
        status, band = "partial", "low"
        summary = (
            "SIMULATED DEMO DATA - not a live price. Simulated farmer quote for "
            f"{market}: {value:g} {unit}, observed {observed.date().isoformat()}."
        )
        evidence_reason = (
            "Quote is explicitly marked as simulated demo data; shown for demonstration "
            "only, provenance is farmer_reported and not independently verified."
        )
        flags = ["simulated_demo_data", "not_official_market_data", "farmer_reported_only"]
        checks = [
            "Use a real observed quote for anything beyond a demo; this one is simulated."
        ]
    else:
        status, band = "complete", "low"
        summary = (
            f"Farmer-reported quote for {market}: {value:g} {unit}, observed "
            f"{observed.date().isoformat()}; not verified against any official market feed."
        )
        evidence_reason = (
            f"Farmer-entered quote within the {stale_days}-day freshness limit; provenance "
            "is farmer_reported and not independently verified."
        )
        flags = ["farmer_reported_only", "not_official_market_data"]
        checks = [
            "Confirm the quote, unit, market, and observation date with the source before relying on it."
        ]

    observations = [
        "Farmer reported this quote; KisanOS did not retrieve or verify it.",
        f"Observed at {observed_text} ({age_days:.1f} day(s) ago).",
    ]
    if amis and amis.get("enabled") and amis.get("attempted"):
        observations.append(AMIS_NOT_AVAILABLE_OBSERVED)

    return AgentResult(
        assessment_id=assessment_id,
        agent_id="market",
        status=status,
        summary=summary,
        observations=observations,
        possible_causes=[],
        checks=checks,
        evidence_band=band,
        evidence_reason=evidence_reason,
        sources=[
            Source(
                title="Farmer-entered market quote",
                publisher="Farmer",
                geography=market,
                retrieved_at=now,
                source_status="farmer_reported",
                note=(
                    "Simulated demo data; not a live market price."
                    if simulated
                    else "User supplied; not independently verified."
                ),
            )
        ],
        provider_or_model="farmer_reported",
        version=VERSION,
        created_at=now,
        safety_flags=flags,
        data={
            "quote": {
                "market": market,
                "value": value,
                "unit": unit,
                "observed_at": observed_text,
            },
            "market": market,
            "value": value,
            "unit": unit,
            "observed_at": observed_text,
            "age_hours": round(age_hours, 1),
            "age_days": round(age_days, 1),
            "freshness": "stale" if stale else "fresh",
            "stale_badge": stale,
            "freshness_limit_days": stale_days,
            "is_official": False,
            "is_simulated": simulated,
            "data_classification": (
                "SIMULATED DEMO DATA" if simulated else "farmer_reported"
            ),
            "adapter": adapter,
            "amis": dict(amis) if amis is not None else dict(NO_AMIS_DIAG),
        },
        input_evidence=["Farmer-entered quote"],
    )


def _amis_result(
    assessment_id: str,
    quote: dict[str, Any],
    now: datetime,
    adapter: dict[str, Any],
    amis: dict[str, Any],
) -> AgentResult:
    """Official AMIS quote -> complete / stale / partial, source-reported.

    The numbers, unit, market, source date and URL come from the AMIS page
    unchanged; only freshness (from the AMIS source date) decides the status so
    an older quote is never presented as current.
    """
    freshness = quote.get("freshness", "unknown")
    market = str(quote["market"])
    unit = str(quote["unit"])
    date_text = str(quote.get("source_date") or "unavailable")
    retrieved_at = str(quote.get("retrieved_at") or now.isoformat())
    source_url = str(quote.get("source_url") or "")

    parts: list[str] = []
    if quote.get("min_price") is not None:
        parts.append(f"min {quote['min_price']:g}")
    if quote.get("max_price") is not None:
        parts.append(f"max {quote['max_price']:g}")
    if quote.get("average_price") is not None:
        parts.append(f"average {quote['average_price']:g}")
    detail = ", ".join(parts)

    observations = [
        AMIS_OBSERVED,
        f"Source date: {date_text}",
        f"Retrieved at: {retrieved_at}",
        f"Source URL: {source_url}",
    ]

    if freshness == "fresh":
        status = "complete"
        freshness_label = "fresh"
        freshness_note = "within 24 hours of the AMIS source date"
        flags = ["amis_source_reported"]
        evidence = AMIS_REASON_FRESH
        checks = [AMIS_CHECK_CONFIRM]
    elif freshness == "stale":
        status = "stale"
        freshness_label = "stale"
        freshness_note = "older than 24 hours, not presented as a current price"
        flags = ["amis_source_reported", "stale_quote"]
        evidence = AMIS_REASON_STALE
        checks = [AMIS_CHECK_FRESHNESS]
        observations.insert(1, AMIS_STALE_OBSERVED)
    else:
        status = "partial"
        freshness_label = "date unavailable"
        freshness_note = "source-reported without a date, not a current-day price"
        flags = ["amis_source_reported", "source_date_missing"]
        evidence = AMIS_REASON_UNKNOWN_DATE
        checks = [AMIS_CHECK_FRESHNESS]
        observations.insert(1, AMIS_NO_DATE_OBSERVED)

    summary = (
        f"AMIS wheat price: {market}, {detail}, unit {unit}, source date {date_text}; "
        f"freshness {freshness_label} ({freshness_note})."
    )

    return AgentResult(
        assessment_id=assessment_id,
        agent_id="market",
        status=status,
        summary=summary,
        observations=observations,
        possible_causes=[],
        checks=checks,
        evidence_band=str(quote.get("evidence_band", "low")),  # type: ignore[arg-type]
        evidence_reason=evidence,
        sources=[
            Source(
                title=AMIS_SOURCE_TITLE,
                url=source_url or None,
                publisher=AMIS_PUBLISHER,
                geography=market,
                published_at=quote.get("quoted_at"),
                retrieved_at=now,
                source_status="official",
                note="Source-reported quote; KisanOS did not independently verify it.",
            )
        ],
        provider_or_model="amis_source_reported",
        version=VERSION,
        created_at=now,
        safety_flags=flags,
        data={
            "quote": dict(quote),
            "freshness": freshness,
            "market": market,
            "commodity": quote.get("commodity"),
            "currency": quote.get("currency"),
            "unit": unit,
            "min_price": quote.get("min_price"),
            "max_price": quote.get("max_price"),
            "average_price": quote.get("average_price"),
            "source_url": source_url,
            "source_date": quote.get("source_date"),
            "quoted_at": quote.get("quoted_at"),
            "retrieved_at": retrieved_at,
            "verification_status": "source_reported",
            "stale_badge": freshness == "stale",
            "is_official": True,
            "is_simulated": False,
            "data_classification": "source_reported",
            "adapter": adapter,
            "amis": dict(amis),
        },
        input_evidence=["Punjab AMIS price page"],
    )


def assess_market(assessment_id: str, intake: dict[str, Any]) -> AgentResult:
    """Deterministic, fail-closed Market card.

    Order: the official Punjab AMIS page when AMIS_ENABLED is set (source
    reported, freshness taken from the AMIS source date), then the
    farmer-entered quote. No usable AMIS quote -> "Price unavailable" with a
    reason; a price is never invented, never substituted from another market,
    and adapter payloads are still never consumed.
    """
    now = datetime.now(UTC)
    settings = get_settings()
    stale_days = settings.market_quote_stale_days
    quote = intake.get("market_quote")

    # 1) Official AMIS source (opt-in, never raises, never invents a price).
    amis_quote, amis_diag = fetch_amis_quote(
        market=amis_requested_market(intake),
        commodity=str(intake.get("crop") or "wheat"),
        now=now,
    )
    if amis_quote is not None:
        return _amis_result(assessment_id, amis_quote, now, adapter_status(), amis_diag)

    # 2) No official quote -> the farmer-entered quote (unchanged, fail-closed).
    if not quote:
        payload, adapter = _probe_adapter(intake, market="")
        return _unavailable_result(
            assessment_id,
            now,
            _no_quote_reason(amis_diag),
            [],
            adapter,
            payload is not None,
            ["No farmer-entered quote"],
            extra_flags=["amis_unavailable"] if amis_diag.get("enabled") else None,
            amis=amis_diag,
        )

    normalized, problems = _validate_quote(quote, now)
    if problems:
        hint = ""
        if isinstance(quote, dict) and isinstance(quote.get("market"), str):
            hint = quote["market"]
        payload, adapter = _probe_adapter(intake, market=hint)
        return _unavailable_result(
            assessment_id,
            now,
            f"the farmer-entered quote failed validation ({', '.join(problems)}); "
            "no price is shown.",
            problems,
            adapter,
            payload is not None,
            ["Farmer-entered quote failed validation"],
            amis=amis_diag,
        )

    # The farmer's own quote takes precedence only when AMIS gave nothing;
    # only report adapter readiness.
    adapter = adapter_status()
    return _quote_result(
        assessment_id, normalized, now, stale_days, adapter, amis=amis_diag
    )

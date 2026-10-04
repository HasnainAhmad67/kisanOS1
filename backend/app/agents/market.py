from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.schemas import AgentResult, Source
from app.services.market_adapter import adapter_status, fetch_market_quote

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
) -> AgentResult:
    flags = ["no_price_invented", *problems]
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
        },
        input_evidence=input_evidence,
    )


def _quote_result(
    assessment_id: str,
    quote: dict[str, Any],
    now: datetime,
    stale_days: int,
    adapter: dict[str, Any],
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

    return AgentResult(
        assessment_id=assessment_id,
        agent_id="market",
        status=status,
        summary=summary,
        observations=[
            "Farmer reported this quote; KisanOS did not retrieve or verify it.",
            f"Observed at {observed_text} ({age_days:.1f} day(s) ago).",
        ],
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
        },
        input_evidence=["Farmer-entered quote"],
    )


def assess_market(assessment_id: str, intake: dict[str, Any]) -> AgentResult:
    """Deterministic, fail-closed Market card.

    No quote (or an invalid one) -> "Price unavailable"; a valid farmer quote
    -> complete/stale with a farmer_reported source and disclosed freshness;
    simulated quotes are tagged SIMULATED DEMO DATA. A price is never
    invented and adapter payloads are never consumed until an AMIS API
    contract is verified.
    """
    now = datetime.now(UTC)
    stale_days = get_settings().market_quote_stale_days
    quote = intake.get("market_quote")

    if not quote:
        payload, adapter = _probe_adapter(intake, market="")
        return _unavailable_result(
            assessment_id,
            now,
            NO_QUOTE_REASON,
            [],
            adapter,
            payload is not None,
            ["No farmer-entered quote"],
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
        )

    # The farmer's own quote takes precedence; only report adapter readiness.
    adapter = adapter_status()
    return _quote_result(assessment_id, normalized, now, stale_days, adapter)

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas import AgentResult, Source

VERSION = "market-safe-adapter-1.0.0"


def assess_market(assessment_id: str, intake: dict[str, Any]) -> AgentResult:
    quote = intake.get("market_quote")
    now = datetime.now(UTC)
    if not quote:
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="market",
            status="unavailable",
            summary="Price unavailable: no verified current AMIS quote or farmer-entered quote was supplied.",
            observations=[],
            possible_causes=[],
            checks=[],
            evidence_band="not_calibrated",
            evidence_reason="No market quote was retrieved or provided; no price is inferred.",
            sources=[],
            provider_or_model="AMIS adapter not configured; fail-closed",
            version=VERSION,
            created_at=now,
            safety_flags=["no_price_invented"],
            data={"quote": None, "freshness": "unavailable"},
            input_evidence=["No farmer-entered quote"],
        )
    observed = quote["observed_at"]
    if isinstance(observed, str):
        observed = (
            datetime.fromisoformat(observed[:-1]).replace(tzinfo=UTC)
            if observed.endswith("Z")
            else datetime.fromisoformat(observed)
        )
    age_hours = max(0.0, (now - observed.astimezone(UTC)).total_seconds() / 3600)
    unit = quote["unit"]
    market = quote["market"]
    value = float(quote["value"])
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="market",
        status="partial",
        summary=f"Farmer-reported quote for {market}: {value:g} {unit}; it is not verified against an official market feed.",
        observations=["Farmer reported this quote; KisanOS did not retrieve or verify it."],
        possible_causes=[],
        checks=["Confirm the quote, unit, market, and observation date with the source before relying on it."],
        evidence_band="low",
        evidence_reason="Farmer-entered market information; provenance is disclosed and not independently verified.",
        sources=[
            Source(
                title="Farmer-entered market quote",
                publisher="Farmer",
                geography=market,
                retrieved_at=now,
                source_status="farmer_reported",
                note="User supplied; not independently verified.",
            )
        ],
        provider_or_model="farmer_reported",
        version=VERSION,
        created_at=now,
        safety_flags=["not_official_market_data", "no_price_prediction"],
        data={
            "market": market,
            "value": value,
            "unit": unit,
            "observed_at": observed.isoformat(),
            "age_hours": round(age_hours, 1),
            "freshness": "reported_timestamp_only",
            "is_official": False,
        },
        input_evidence=["Farmer-entered quote"],
    )

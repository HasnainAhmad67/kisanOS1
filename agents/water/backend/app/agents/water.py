from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas import AgentResult, Source
from app.team_agents.water.agent import evaluate_water


def assess_water(
    assessment_id: str,
    intake: dict[str, Any],
    weather: AgentResult | dict[str, Any] | None = None,
) -> AgentResult:
    """
    Adapt the deterministic Water Agent core to KisanOS's
    shared AgentResult schema.

    The Water Agent uses weather information only as contextual
    evidence for the rainfall re-check policy. It does not create
    numeric irrigation thresholds or direct irrigation commands.
    """

    # Run the canonical Water Agent policy.
    decision = evaluate_water(
        intake,
        weather=weather,
        assessment_id=assessment_id,
    )

    # Convert source dictionaries into the shared Source model.
    sources = [
        Source.model_validate(source)
        for source in decision.get("sources", [])
    ]

    # Convert ISO timestamp from the Water Agent into datetime.
    created_at_text = decision.get("created_at")

    if isinstance(created_at_text, datetime):
        created_at = created_at_text
    elif created_at_text:
        created_at = datetime.fromisoformat(created_at_text)
    else:
        created_at = datetime.now().astimezone()

    # Keep all Water-specific backend information.
    backend_data = decision.get("backend_data", {})

    # Convert the Water Agent output into KisanOS's shared result schema.
    return AgentResult(
        assessment_id=decision["assessment_id"],
        agent_id=decision["agent_id"],
        status=decision["status"],
        summary=decision["summary"],
        observations=decision["observations"],
        possible_causes=decision["possible_causes"],
        checks=decision["checks"],
        evidence_band=decision["evidence_band"],
        evidence_reason=decision["evidence_reason"],
        sources=sources,
        provider_or_model=decision["provider_or_model"],
        version=decision["version"],
        created_at=created_at,
        safety_flags=decision["safety_flags"],
        data=backend_data,
        input_evidence=decision.get("input_evidence", []),
    )
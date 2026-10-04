from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas import AgentResult, Source
from app.services.weather_panel import normalize_weather_for_water
from app.team_agents.water.agent import evaluate_water


def assess_water(
    assessment_id: str,
    intake: dict[str, Any],
    weather: AgentResult | dict[str, Any] | None = None,
) -> AgentResult:
    """
    Thin adapter: intake + Weather AgentResult -> Water v2.0.0 -> AgentResult.

    Water v2.0.0 (app.team_agents.water.agent, policy
    "kisanos-water-conservative-v2") owns the water policy. This adapter only:

      1. normalizes the connected Weather AgentResult into the dated
         forecast-panel shape Water v2.0.0 expects
         (app.services.weather_panel.normalize_weather_for_water), and
      2. converts Water's decision dict into the shared backend AgentResult.

    It never re-implements or overrides any water decision.
    """

    weather_panel = normalize_weather_for_water(weather)

    decision = evaluate_water(
        intake,
        weather=weather_panel,
        assessment_id=assessment_id,
    )

    sources = [
        Source.model_validate(source)
        for source in decision.get("sources", [])
    ]

    created_at_value = decision.get("created_at")

    if isinstance(created_at_value, datetime):
        created_at = created_at_value
    elif created_at_value:
        created_at = datetime.fromisoformat(created_at_value)
    else:
        created_at = datetime.now().astimezone()

    backend_data = decision.get("backend_data", {})

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

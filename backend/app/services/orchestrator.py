from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.agents.advisor import build_farm_plan
from app.agents.crop import assess_crop
from app.agents.market import assess_market
from app.agents.vision import analyze_images
from app.agents.water import assess_water
from app.agents.weather import assess_weather
from app.core.config import get_settings
from app.db import AssessmentRow, ImageRow, JobRow, SessionLocal
from app.schemas import AgentResult, AIExplanation, AssessmentResults
from app.services.gemini_explainer import explain_farm_plan

logger = logging.getLogger("kisanos.orchestrator")
_ACTIVE: dict[str, asyncio.Task] = {}
_AGENT_LIMIT = asyncio.Semaphore(5)


def now() -> datetime:
    return datetime.now(UTC)


def _json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _append_event(
    job_id: str, phase: str, status: str, detail: str | None = None
) -> None:
    with SessionLocal() as db:
        row = db.get(JobRow, job_id)
        if not row:
            return
        events = list(row.events or [])
        events.append(
            {
                "sequence": len(events) + 1,
                "phase": phase,
                "status": status,
                "timestamp": now().isoformat(),
                "detail": detail,
            }
        )
        row.events = events
        row.updated_at = now()
        db.commit()


def _set_job(
    job_id: str, state: str, result: dict | None = None, error_code: str | None = None
) -> None:
    with SessionLocal() as db:
        row = db.get(JobRow, job_id)
        if row:
            row.state, row.updated_at = state, now()
            if result is not None:
                row.result = result
            row.error_code = error_code
            db.commit()


def create_analysis_job(assessment_id: str) -> str:
    job_id = str(uuid.uuid4())
    with SessionLocal() as db:
        job = JobRow(
            id=job_id,
            assessment_id=assessment_id,
            state="queued",
            events=[],
            created_at=now(),
            updated_at=now(),
        )
        db.add(job)
        assessment = db.get(AssessmentRow, assessment_id)
        assessment.state = "queued"
        assessment.updated_at = now()
        db.commit()
    _ACTIVE[job_id] = asyncio.create_task(
        _run_job(job_id), name=f"kisanos-analysis-{job_id}"
    )
    return job_id


def _unavailable(
    assessment_id: str, agent_id: str, message: str, reason: str
) -> AgentResult:
    return AgentResult(
        assessment_id=assessment_id,
        agent_id=agent_id,
        status="unavailable",
        summary=message,
        evidence_reason=reason,
        provider_or_model="policy-gated-adapter",
        version="1.0.0",
        created_at=now(),
        safety_flags=["agent_error_isolated"],
    )


async def _tracked(
    job_id: str, name: str, fn: Callable[[], Awaitable[AgentResult]]
) -> AgentResult:
    _append_event(job_id, name, "started")
    try:
        async with _AGENT_LIMIT:
            result = await asyncio.wait_for(
                fn(), timeout=get_settings().agent_timeout_seconds
            )
        event_state = (
            "completed" if result.status in {"complete", "partial"} else "unavailable"
        )
        _append_event(job_id, name, event_state, result.status)
        return result
    except Exception as exc:  # noqa: BLE001 - isolate specialist faults; other agents and the Farm Plan continue.
        logger.warning(
            "agent execution failed",
            extra={
                "job_id": job_id,
                "agent_id": name,
                "error_type": type(exc).__name__,
            },
        )
        _append_event(job_id, name, "failed", type(exc).__name__)
        assessment_id = _job_assessment_id(job_id)
        return _unavailable(
            assessment_id,
            name,
            f"{name.title()} agent is unavailable; other agents continued.",
            f"Agent exception ({type(exc).__name__}); no result accepted.",
        )


def _job_assessment_id(job_id: str) -> str:
    with SessionLocal() as db:
        job = db.get(JobRow, job_id)
        return job.assessment_id if job else "00000000-0000-4000-8000-000000000000"


def _load_context(job_id: str) -> tuple[str, dict, list[dict]]:
    with SessionLocal() as db:
        job = db.get(JobRow, job_id)
        assessment = db.get(AssessmentRow, job.assessment_id)
        images = (
            db.query(ImageRow).filter(ImageRow.assessment_id == assessment.id).all()
        )
        intake = dict(assessment.payload)
        records = []
        root = get_settings().image_storage_dir.resolve()
        for image in images:
            path = (root / image.storage_key).resolve()
            if root not in path.parents:
                continue
            records.append(
                {
                    "id": image.id,
                    "view_type": image.view_type,
                    "quality": image.quality,
                    "read_bytes": lambda p=path: p.read_bytes(),
                }
            )
        return assessment.id, intake, records


async def _run_job(job_id: str) -> None:
    assessment_id = _job_assessment_id(job_id)
    try:
        _set_job(job_id, "running")
        with SessionLocal() as db:
            assessment = db.get(AssessmentRow, assessment_id)
            assessment.state = "running"
            assessment.updated_at = now()
            db.commit()
        assessment_id, intake, images = _load_context(job_id)
        _append_event(job_id, "quality_gate", "started")
        quality_pass_count = sum(
            bool(image["quality"].get("passed")) for image in images
        )
        _append_event(
            job_id,
            "quality_gate",
            "completed",
            f"{quality_pass_count}/{len(images)} photos passed; quality is not a symptom diagnosis",
        )

        # Independent agents run concurrently; no agent reads another agent's hidden state.
        weather, vision, market = await asyncio.gather(
            _tracked(job_id, "weather", lambda: assess_weather(assessment_id, intake)),
            _tracked(
                job_id, "vision", lambda: analyze_images(assessment_id, intake, images)
            ),
            _tracked(
                job_id,
                "market",
                lambda: asyncio.to_thread(assess_market, assessment_id, intake),
            ),
        )
        _append_event(job_id, "crop", "started")
        crop = await asyncio.to_thread(assess_crop, assessment_id, intake, vision)
        _append_event(job_id, "crop", "completed", crop.status)
        _append_event(job_id, "water", "started")
        water = await asyncio.to_thread(assess_water, assessment_id, intake, weather)
        _append_event(job_id, "water", "completed", water.status)
        agents = [weather, water, crop, vision, market]
        _append_event(job_id, "policy_gate", "started")
        # Schema validation is repeated at the boundary; failure is isolated as explicit abstention.
        for index, item in enumerate(agents):
            try:
                agents[index] = AgentResult.model_validate(_json(item))
            except Exception:  # noqa: BLE001 - reject any invalid specialist envelope at the policy boundary.
                agents[index] = _unavailable(
                    assessment_id,
                    item.agent_id,
                    f"{item.agent_id.title()} result failed contract validation; it was not used.",
                    "Invalid agent envelope.",
                )
        _append_event(
            job_id,
            "policy_gate",
            "completed",
            "Agent contracts validated; unsafe legacy thresholds and demo model outputs are not used",
        )
        _append_event(job_id, "farm_advisor", "started")
        plan = build_farm_plan(assessment_id, intake, agents)
        _append_event(job_id, "farm_advisor", "completed", plan.status)

        # Gemini explains the existing Farm Plan only; it cannot change agent evidence,
        # check titles, check order, priorities, or the assessment status.
        _append_event(job_id, "gemini_explanation", "started")
        try:
            ai_explanation = await explain_farm_plan(intake, agents, plan)
        except Exception as exc:  # noqa: BLE001 - optional Gemini must never fail the analysis job.
            logger.warning(
                "Gemini explanation phase failed",
                extra={"error_type": type(exc).__name__},
            )
            locale = intake.get("locale", "en")
            if locale not in {"en", "ur", "roman_ur"}:
                locale = "en"
            ai_explanation = AIExplanation(
                status="unavailable",
                locale=locale,
                reason="provider_error",
            )

        explanation_event_status = {
            "complete": "completed",
            "skipped": "skipped",
            "unavailable": "unavailable",
        }[ai_explanation.status]
        _append_event(
            job_id,
            "gemini_explanation",
            explanation_event_status,
            ai_explanation.reason or ai_explanation.status,
        )

        result = AssessmentResults(
            assessment_id=assessment_id,
            job_id=job_id,
            status="complete"
            if all(a.status == "complete" for a in agents)
            else "partial",
            created_at=now(),
            agents=agents,
            farm_plan=plan,
            ai_explanation=ai_explanation,
            input_recap={
                "crop": intake["crop"],
                "area_code": intake["area_code"],
                "growth_stage": intake["growth_stage"],
                "irrigation_history": intake["irrigation_history"],
                "symptom_onset": intake["symptom_onset"],
                "symptoms_spreading": intake["symptoms_spreading"],
                "photo_count": len(images),
                "notes_included": bool(intake.get("notes")),
            },
            local_timezone=intake.get("timezone", "Asia/Karachi"),
        )
        payload = _json(result)
        state = "succeeded" if result.status == "complete" else "partial"
        _set_job(job_id, state, payload)
        with SessionLocal() as db:
            assessment = db.get(AssessmentRow, assessment_id)
            if assessment:
                assessment.state = state
                assessment.updated_at = now()
                db.commit()
    except Exception as exc:
        logger.exception(
            "analysis job failed",
            extra={
                "job_id": job_id,
                "assessment_id": assessment_id,
                "error_type": type(exc).__name__,
            },
        )
        _append_event(job_id, "analysis", "failed", type(exc).__name__)
        _set_job(job_id, "failed", error_code="analysis_failed")
        with SessionLocal() as db:
            assessment = db.get(AssessmentRow, assessment_id)
            if assessment:
                assessment.state = "failed"
                assessment.updated_at = now()
                db.commit()
    finally:
        _ACTIVE.pop(job_id, None)

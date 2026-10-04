from __future__ import annotations

import asyncio
import io
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from PIL import Image, ImageOps

from app.core.config import get_settings
from app.schemas import AgentResult, Source
from app.services.vision_inference import predict_locally
from app.team_agents.vision.quality import check_quality

VERSION = "vision-gateway-1.0.0"
ALLOWED_CLASSES = {
    "healthy_looking",
    "yellowing",
    "rust_like_pustules",
    "spots_or_blotches",
    "visible_insects",
    "drying",
    "unclear",
}
LABELS = {
    "healthy_looking": "No clear visible symptoms",
    "yellowing": "Visible yellowing",
    "rust_like_pustules": "Rust-like marks visible; cause not confirmed",
    "spots_or_blotches": "Visible spots or blotches",
    "visible_insects": "Visible insects",
    "drying": "Visible drying",
    "unclear": "Image details unclear",
}
UNSAFE_MODEL_TEXT = re.compile(
    r"\b(diagnos\w*|confirm\w*|definit\w*|pesticid\w*|fungicid\w*|insecticid\w*|herbicid\w*|chemical\w*|spray\w*|dose\w*|urea|dap|treat\w*|infection\w*|pathogen\w*|irrigat\w*|yield\w*|guarantee\w*|cure\w*|recommend\w*)\b",
    re.IGNORECASE,
)


def _safe_image_bytes(raw: bytes) -> tuple[bytes, str]:
    # Re-encoding strips EXIF/GPS and normalizes orientation before private storage/inference.
    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600, 1600))
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=88, optimize=True)
        return out.getvalue(), "image/jpeg"


async def _fetch_remote_prediction(
    settings: Any, assessment_id: str, intake: dict[str, Any], passed: list[dict[str, Any]]
) -> dict[str, Any]:
    """POST quality-passed photos to the operator-configured private endpoint."""
    contents = []
    for item in passed:
        clean, mime = await asyncio.to_thread(_safe_image_bytes, item["raw"])
        contents.append(("files", (f"{item['record']['id']}.jpg", clean, mime)))
    fields = {
        "assessment_id": assessment_id,
        "crop": "wheat",
        "growth_stage": intake.get("growth_stage", "not_sure"),
        "contract_version": "kisanos-agent-v1",
    }
    headers = {"Authorization": f"Bearer {settings.vision_inference_token}"} if settings.vision_inference_token else {}
    async with httpx.AsyncClient(timeout=settings.agent_timeout_seconds, follow_redirects=False) as client:
        response = await client.post(settings.vision_inference_url, data=fields, files=contents, headers=headers)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("model response must be a JSON object")
    return payload


def _model_unavailable_result(
    assessment_id: str, passed: list[dict[str, Any]], now: datetime, reason: str
) -> AgentResult:
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="vision",
        status="unavailable",
        summary="The private vision inference service was unavailable or returned an invalid response; no model finding was accepted.",
        observations=["Photo quality checks passed; model output was not available."],
        checks=["Continue using farmer-entered symptoms or retry the private model later."],
        evidence_band="not_calibrated",
        evidence_reason=reason,
        provider_or_model="self-hosted-unavailable",
        version=VERSION,
        created_at=now,
        safety_flags=["model_unavailable", "invalid_output_rejected"],
        data={"quality_passed": True, "image_ids": [item["record"]["id"] for item in passed]},
        input_evidence=["Quality-approved photos; no valid model response"],
    )


def _no_model_configured_result(
    assessment_id: str, passed: list[dict[str, Any]], now: datetime, reason: str
) -> AgentResult:
    """Safe fallback: quality passed but no model artifacts / endpoint exist."""
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="vision",
        status="not_assessed",
        summary="Photo quality passed, but no self-hosted vision model is configured; no example or simulated model result is shown.",
        observations=["At least one photo passed the supplied image-quality gate."],
        checks=["Connect the approved private vision inference service, or continue with farmer-entered symptoms."],
        evidence_band="not_calibrated",
        evidence_reason="Quality checks do not identify symptoms; inference is unavailable.",
        provider_or_model="team-vision-quality-gate; inference not configured",
        version=VERSION,
        created_at=now,
        safety_flags=["model_unavailable", "no_dummy_output_used"],
        data={
            "quality_passed": True,
            "images_accepted": len(passed),
            "image_ids": [item["record"]["id"] for item in passed],
            "model_integration": {
                "state": "not_available",
                "plug_in_point": "app.services.vision_inference:predict_locally",
                "reason": reason,
            },
        },
        input_evidence=["Image quality gate passed; no model output"],
    )


def _accept_prediction(
    assessment_id: str, payload: dict[str, Any], passed: list[dict[str, Any]], now: datetime
) -> AgentResult:
    """Validate a model prediction and build the result. Fail-closed on any
    unsupported content: non-wheat crop, unsafe text, or malformed output.

    Shared by the private HTTP endpoint and (future) local model inference.
    Raises ValueError/KeyError/TypeError/AttributeError on malformed payloads;
    callers map that to an explicit abstention.
    """
    crop_detected = payload.get("crop_detected")
    if crop_detected != "wheat":
        status = "unsupported" if crop_detected else "unavailable"
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status=status,
            summary="The vision result did not establish a supported wheat photo; no visible symptom finding was accepted.",
            evidence_reason="The private model must return crop_detected='wheat'; missing or unsupported crop output abstains.",
            provider_or_model="self-hosted-rejected",
            version=VERSION,
            created_at=now,
            safety_flags=["wheat_scope_gate", "no_interpretation_accepted"],
            data={"quality_passed": True, "image_ids": [item["record"]["id"] for item in passed]},
            input_evidence=["Quality-approved photos; crop check not passed"],
        )
    findings = payload.get("visible_findings", [])
    observations, seen = [], set()
    for finding in findings[:8]:
        label = finding.get("class") if isinstance(finding, dict) else None
        if label not in ALLOWED_CLASSES:
            continue
        detail = str(finding.get("detail", "visible sign noted"))[:180]
        if UNSAFE_MODEL_TEXT.search(detail):
            return AgentResult(
                assessment_id=assessment_id,
                agent_id="vision",
                status="unavailable",
                summary="The model response did not pass the safety gate; no visual interpretation was accepted.",
                evidence_reason="A model output contained unsupported diagnostic or action language and was rejected.",
                provider_or_model="self-hosted-rejected",
                version=VERSION,
                created_at=now,
                safety_flags=["unsafe_model_text_rejected", "no_interpretation_accepted"],
                data={"quality_passed": True, "image_ids": [item["record"]["id"] for item in passed]},
                input_evidence=["Quality-approved photos; model response rejected"],
            )
        safe = f"{LABELS[label]}: {detail}"
        if safe not in seen:
            observations.append(safe)
            seen.add(safe)
    if not observations:
        observations = ["The model did not return a supported visible finding."]
    # The model is uncalibrated locally: confidence is capped at medium and never a disease probability.
    evidence_band = "medium" if len(passed) >= 2 and payload.get("confidence") == "medium" else "low"
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="vision",
        status="complete",
        summary="Photos can describe visible signs only and cannot confirm their cause.",
        observations=observations,
        possible_causes=[],
        checks=["Compare the visible pattern on several plants and inspect both sides of affected leaves."],
        evidence_band=evidence_band,
        evidence_reason="Uncalibrated self-hosted model output; evidence band describes image evidence quality, not disease probability. Confidence is capped at medium.",
        sources=[
            Source(
                title="Self-hosted KisanOS vision inference",
                publisher="Configured private model service",
                source_status="unverified",
                note="Model artifact and locally validated performance must be recorded by deployment.",
            )
        ],
        provider_or_model="self-hosted",
        version=str(payload.get("model_version", VERSION))[:80],
        created_at=now,
        safety_flags=["not_a_diagnosis", "local_validation_pending", "confidence_capped_at_medium"],
        data={
            "quality_passed": True,
            "images_accepted": len(passed),
            "image_ids": [item["record"]["id"] for item in passed],
            "model_version": str(payload.get("model_version", "not reported"))[:80],
        },
        input_evidence=["Quality-approved uploaded wheat photos"],
    )


async def analyze_images(
    assessment_id: str, intake: dict[str, Any], image_records: list[dict[str, Any]]
) -> AgentResult:
    now = datetime.now(UTC)
    if not image_records:
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status="not_assessed",
            summary="Vision was not assessed because no photo was supplied.",
            evidence_reason="No image evidence.",
            provider_or_model="not_configured",
            version=VERSION,
            created_at=now,
            safety_flags=["manual_fallback_available"],
            input_evidence=["No photos supplied"],
        )

    checked = []
    failures = []
    for record in image_records[:4]:
        try:
            raw = await asyncio.to_thread(record["read_bytes"])
            quality = await asyncio.to_thread(check_quality, raw)
            checked.append({"record": record, "raw": raw, "quality": quality})
            if not quality.get("passed"):
                failures.extend(quality.get("issues", []))
        except (OSError, KeyError, TypeError):
            failures.append("image_unreadable")
    passed = [item for item in checked if item["quality"].get("passed")]
    if not passed:
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status="not_assessed",
            summary="No uploaded photo passed the image-quality checks; no visual interpretation was made.",
            observations=[f"Photo quality issue: {issue.replace('_', ' ')}" for issue in sorted(set(failures))],
            checks=[
                "Retake a close-up in daylight with the affected plant part in focus, or continue using farmer-entered observations."
            ],
            evidence_band="not_calibrated",
            evidence_reason="The uploaded image(s) failed the supplied team's quality gate.",
            provider_or_model="team-vision-quality-gate",
            version=VERSION,
            created_at=now,
            safety_flags=["photo_quality_failed", "no_visual_analysis_performed"],
            data={"quality_passed": False, "quality_issues": sorted(set(failures)), "image_ids": [item["record"]["id"] for item in checked]},
            input_evidence=["Uploaded photos did not pass image-quality checks"],
        )

    settings = get_settings()
    if settings.vision_inference_url:
        # The only path that receives images is an operator-configured private self-hosted endpoint.
        try:
            payload = await _fetch_remote_prediction(settings, assessment_id, intake, passed)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, OSError):
            return _model_unavailable_result(
                assessment_id,
                passed,
                now,
                "Service error or schema mismatch; output safely abstained.",
            )
    else:
        # Local model plug-in point (app.services.vision_inference).
        # No artifacts are shipped today, so this returns (None, reason) and
        # Vision stays in safe fallback - never a dummy or example result.
        try:
            payload, reason = predict_locally([item["raw"] for item in passed], intake)
        except Exception:  # noqa: BLE001 - a broken loader must never crash the pipeline.
            payload, reason = None, "local model inference raised an unexpected error; no result was used"
        if payload is None:
            return _no_model_configured_result(
                assessment_id, passed, now, reason or "local model inference is not configured"
            )

    try:
        return _accept_prediction(assessment_id, payload, passed, now)
    except (ValueError, KeyError, TypeError, AttributeError):
        return _model_unavailable_result(
            assessment_id,
            passed,
            now,
            "Service error or schema mismatch; output safely abstained.",
        )

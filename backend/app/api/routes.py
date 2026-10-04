from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import os
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import desc, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import AREAS, get_settings
from app.core.security import new_access_token, require_assessment_token, token_digest
from app.core.sources import source_registry
from app.db import AssessmentRow, FollowUpRow, ImageRow, JobRow, SessionLocal
from app.schemas import AssessmentCreate, AssessmentCreated, FollowUpCreate
from app.services.orchestrator import create_analysis_job
from app.team_agents.vision.quality import check_quality

router = APIRouter()


def _now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "assessment_not_found", "message": "Assessment was not found."}
    )


def _auth_job(job_id: str, token: str | None) -> JobRow:
    if not token:
        raise HTTPException(
            status_code=401, detail={"code": "assessment_token_required", "message": "Provide X-Assessment-Token."}
        )
    with SessionLocal() as db:
        job = db.get(JobRow, job_id)
        if job is None:
            raise HTTPException(
                status_code=404, detail={"code": "job_not_found", "message": "Analysis job was not found."}
            )
        assessment = db.get(AssessmentRow, job.assessment_id)
        if assessment is None:
            raise _not_found()
        if not hmac.compare_digest(assessment.token_hash, token_digest(token)):
            raise HTTPException(
                status_code=403,
                detail={"code": "assessment_token_invalid", "message": "The assessment token is not valid."},
            )
        db.expunge(job)
        return job


def _create_record(payload: AssessmentCreate) -> tuple[str, str, datetime]:
    assessment_id = str(uuid.uuid4())
    token = new_access_token()
    created = _now()
    data = payload.model_dump(mode="json")
    data["policy_version"] = get_settings().policy_version
    data["source_registry_version"] = get_settings().source_registry_version
    data["created_at"] = created.isoformat()
    data["demo_mode"] = get_settings().demo_mode
    row = AssessmentRow(
        id=assessment_id,
        token_hash=token_digest(token),
        payload=data,
        state="created",
        created_at=created,
        updated_at=created,
    )
    with SessionLocal() as db:
        db.add(row)
        db.commit()
    return assessment_id, token, created


@router.get("/health/live", tags=["health"])
def live():
    return {"status": "ok", "service": "kisanos-api", "timestamp": _now().isoformat()}


@router.get("/health/ready", tags=["health"])
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "reachable", "timestamp": _now().isoformat()}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail={"code": "database_unavailable", "message": type(exc).__name__})


@router.get("/config", tags=["meta"])
def public_config():
    settings = get_settings()
    return {
        "product": "KisanOS",
        "api_version": "v1",
        "supported_crop": "wheat",
        "supported_areas": [{"code": code, "name": area["name"]} for code, area in AREAS.items()],
        "policy_version": settings.policy_version,
        "source_registry_version": settings.source_registry_version,
        "photo_limit_bytes": settings.max_upload_bytes,
        "max_photos": settings.max_images_per_assessment,
        "vision_mode": "private_self_hosted" if settings.vision_inference_url else "quality_gate_only_no_model",
        "market_mode": "farmer_reported_only_until_AMIS_API_contract_is_verified",
        "retention_hours": settings.image_retention_hours,
        "safety_notice": "Screening and decision support only; not a confirmed diagnosis or an irrigation or chemical instruction.",
    }


@router.post("/assessments", response_model=AssessmentCreated, status_code=201, tags=["assessments"])
def create_assessment(payload: AssessmentCreate):
    if str(payload.area_code) not in AREAS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_area",
                "message": "This area is outside configured Bahawalpur pilot coverage.",
            },
        )
    if payload.latitude is not None:
        # Coordinate is used only with consent and must be near the configured pilot towns.
        candidates = [(float(a["lat"]), float(a["lon"])) for a in AREAS.values()]
        near = any(
            ((payload.latitude - lat) ** 2 + (payload.longitude - lon) ** 2) ** 0.5 <= 0.75 for lat, lon in candidates
        )
        if not near:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "coordinates_outside_pilot",
                    "message": "Consented coordinates are outside the configured Bahawalpur pilot area.",
                },
            )
    settings = get_settings()
    if payload.consent_version != settings.consent_version:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "consent_version_mismatch",
                "message": "Please review the current privacy notice and submit its consent version.",
            },
        )
    assessment_id, token, created = _create_record(payload)
    return AssessmentCreated(
        assessment_id=assessment_id,
        access_token=token,
        created_at=created,
        supported_areas=list(AREAS),
        policy_version=settings.policy_version,
        retention_hours=settings.image_retention_hours,
        safety_notice="This is screening and decision support, not a confirmed diagnosis. A photo alone cannot confirm cause.",
    )


@router.get("/assessments/{assessment_id}", tags=["assessments"])
def get_assessment(assessment_id: str, row: Annotated[AssessmentRow, Depends(require_assessment_token)]):
    payload = row.payload
    return {
        "assessment_id": row.id,
        "state": row.state,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "crop": payload["crop"],
        "area_code": payload["area_code"],
        "growth_stage": payload["growth_stage"],
        "policy_version": payload.get("policy_version"),
        "image_count": _image_count(assessment_id),
    }


def _image_count(assessment_id: str) -> int:
    with SessionLocal() as db:
        return db.query(ImageRow).filter(ImageRow.assessment_id == assessment_id).count()


@router.post("/assessments/{assessment_id}/images", status_code=201, tags=["images"])
async def upload_image(
    assessment_id: str,
    row: Annotated[AssessmentRow, Depends(require_assessment_token)],
    file: Annotated[UploadFile, File(...)],
    view_type: Annotated[Literal["symptom_closeup", "field_context", "whole_plant", "healthy_comparison"], Form()],
):
    settings = get_settings()
    with SessionLocal() as db:
        count = db.query(ImageRow).filter(ImageRow.assessment_id == assessment_id).count()
    if count >= settings.max_images_per_assessment:
        raise HTTPException(
            status_code=413,
            detail={"code": "image_count_limit", "message": "The configured photo limit has been reached."},
        )
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(
            status_code=415, detail={"code": "unsupported_image_type", "message": "Upload a JPEG or PNG image."}
        )
    raw = await file.read(settings.max_upload_bytes + 1)
    if not raw or len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail={"code": "image_size_limit", "message": "The image is empty or exceeds the configured size limit."},
        )
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = image.size
            if width > 10000 or height > 10000 or width * height > 40_000_000:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "image_dimensions_limit",
                        "message": "The image dimensions exceed the safe processing limit.",
                    },
                )
            image.thumbnail((2400, 2400))
            cleaned = io.BytesIO()
            image.save(cleaned, format="JPEG", quality=90, optimize=True)
            clean_bytes = cleaned.getvalue()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=415,
            detail={"code": "invalid_image", "message": "The uploaded bytes are not a valid JPEG or PNG image."},
        )
    quality = await asyncio.to_thread(check_quality, clean_bytes)
    image_id = str(uuid.uuid4())
    key = f"{assessment_id}/{image_id}.jpg"
    root = settings.image_storage_dir.resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_storage_key", "message": "Image storage path rejected."}
        )
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(clean_bytes)
        row_image = ImageRow(
            id=image_id,
            assessment_id=assessment_id,
            storage_key=key,
            view_type=view_type,
            mime_type="image/jpeg",
            byte_size=len(clean_bytes),
            sha256=hashlib.sha256(clean_bytes).hexdigest(),
            width=width,
            height=height,
            quality=quality,
            created_at=_now(),
        )
        with SessionLocal() as db:
            db.add(row_image)
            db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {
        "image_id": image_id,
        "view_type": view_type,
        "mime_type": "image/jpeg",
        "byte_size": len(clean_bytes),
        "sha256": row_image.sha256,
        "dimensions": {"width": width, "height": height},
        "quality": quality,
        "private_storage": True,
        "exif_removed": True,
        "retention_hours": settings.image_retention_hours,
    }


@router.post("/assessments/{assessment_id}/analyze", status_code=202, tags=["analysis"])
async def analyze(assessment_id: str, row: Annotated[AssessmentRow, Depends(require_assessment_token)]):
    with SessionLocal() as db:
        active = (
            db.query(JobRow)
            .filter(JobRow.assessment_id == assessment_id, JobRow.state.in_(["queued", "running"]))
            .order_by(desc(JobRow.created_at))
            .first()
        )
        if active:
            return {
                "job_id": active.id,
                "state": active.state,
                "status_url": f"/api/v1/jobs/{active.id}",
                "reused_active_job": True,
            }
    job_id = create_analysis_job(assessment_id)
    return {"job_id": job_id, "state": "queued", "status_url": f"/api/v1/jobs/{job_id}", "reused_active_job": False}


@router.get("/jobs/{job_id}", tags=["analysis"])
def get_job(job_id: str, x_assessment_token: Annotated[str | None, Header()] = None):
    job = _auth_job(job_id, x_assessment_token)
    return {
        "job_id": job.id,
        "assessment_id": job.assessment_id,
        "state": job.state,
        "events": job.events or [],
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "error_code": job.error_code,
    }


@router.get("/assessments/{assessment_id}/results", tags=["analysis"])
def get_results(assessment_id: str, row: Annotated[AssessmentRow, Depends(require_assessment_token)]):
    with SessionLocal() as db:
        job = db.query(JobRow).filter(JobRow.assessment_id == assessment_id).order_by(desc(JobRow.created_at)).first()
        if job is None:
            raise HTTPException(
                status_code=404, detail={"code": "results_not_ready", "message": "No analysis job has been started."}
            )
        if job.result is None:
            return {
                "assessment_id": assessment_id,
                "job_id": job.id,
                "status": job.state,
                "agents": [],
                "farm_plan": None,
                "events": job.events or [],
            }
        return job.result


@router.post("/assessments/{assessment_id}/followups", status_code=201, tags=["follow-ups"])
def create_followup(
    assessment_id: str, payload: FollowUpCreate, row: Annotated[AssessmentRow, Depends(require_assessment_token)]
):
    followup_id = str(uuid.uuid4())
    with SessionLocal() as db:
        item = FollowUpRow(
            id=followup_id, assessment_id=assessment_id, payload=payload.model_dump(mode="json"), created_at=_now()
        )
        db.add(item)
        db.commit()
    return {
        "followup_id": followup_id,
        "assessment_id": assessment_id,
        "created_at": _now(),
        "note_saved": True,
        "message": "Follow-up saved as a new timestamped farmer observation; it does not prove progression.",
    }


@router.get("/assessments/{assessment_id}/followups", tags=["follow-ups"])
def list_followups(assessment_id: str, row: Annotated[AssessmentRow, Depends(require_assessment_token)]):
    with SessionLocal() as db:
        items = (
            db.query(FollowUpRow)
            .filter(FollowUpRow.assessment_id == assessment_id)
            .order_by(FollowUpRow.created_at)
            .all()
        )
        return [{"followup_id": item.id, "created_at": item.created_at, **item.payload} for item in items]


@router.delete("/assessments/{assessment_id}", tags=["assessments"])
def delete_assessment(assessment_id: str, row: Annotated[AssessmentRow, Depends(require_assessment_token)]):
    settings = get_settings()
    with SessionLocal() as db:
        images = db.query(ImageRow).filter(ImageRow.assessment_id == assessment_id).all()
        deleted_images = 0
        root = settings.image_storage_dir.resolve()
        for image in images:
            path = (root / image.storage_key).resolve()
            if root in path.parents:
                path.unlink(missing_ok=True)
                deleted_images += 1
        db.query(FollowUpRow).filter(FollowUpRow.assessment_id == assessment_id).delete(synchronize_session=False)
        db.query(JobRow).filter(JobRow.assessment_id == assessment_id).delete(synchronize_session=False)
        db.query(ImageRow).filter(ImageRow.assessment_id == assessment_id).delete(synchronize_session=False)
        record = db.get(AssessmentRow, assessment_id)
        db.delete(record)
        db.commit()
    return {
        "assessment_id": assessment_id,
        "deleted": True,
        "linked_images_deleted": deleted_images,
        "message": "Assessment metadata, agent results, follow-ups and linked private images were deleted.",
    }


@router.get("/sources", tags=["sources"])
def get_sources():
    return source_registry()


@router.post("/demo/seed", status_code=201, tags=["demo"])
async def seed_demo():
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail={"code": "demo_disabled", "message": "Demo seeding is disabled."})
    payload = AssessmentCreate(
        crop="wheat",
        crop_confirmed=True,
        area_code="bahawalpur_sadar",
        area_confirmed=True,
        growth_stage="not_sure",
        irrigation_history="not_sure",
        soil_moisture="not_sure",
        drainage="not_sure",
        symptom_onset="recent",
        symptoms_spreading="not_sure",
        symptoms=["yellowing", "spots"],
        notes=None,
        locale="en",
        consent_given=True,
        consent_version=settings.consent_version,
    )
    assessment_id, token, _created = _create_record(payload)
    job_id = create_analysis_job(assessment_id)
    return {
        "assessment_id": assessment_id,
        "access_token": token,
        "job_id": job_id,
        "demo_fixture": "SIMULATED INPUT SCENARIO (SIMULATED DEMO DATA) — no simulated weather, market price, or vision finding is inserted.",
        "status_url": f"/api/v1/jobs/{job_id}",
        "results_url": f"/api/v1/assessments/{assessment_id}/results",
    }

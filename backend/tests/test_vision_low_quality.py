"""Low-quality photo policy: hard block vs soft low-confidence screening.

Covers the spec's minimal test list:
- 96x96 decodable image -> runs the model, returns partial + low evidence
- 200x200 compressed image -> runs the model
- tiny / corrupt / black image -> hard-blocked (no model run)
- a low-quality result never has medium/high confidence
- a low-quality result never uses diagnosis / chemical / spray language
- Crop consumes soft-warning Vision output as low-evidence photo_visible
- existing clear-photo behavior is unchanged
"""

from __future__ import annotations

import asyncio
import io
import re
from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
from PIL import Image

from app.agents import vision as vision_adapter
from app.agents.crop import assess_crop
from app.schemas import AgentResult

AID = "33333333-3333-4333-8333-333333333333"

# Diagnosis / chemical / spray language that must never appear.
# ("confirm" is deliberately excluded: symptom labels legitimately say
# "cause not confirmed", which is a disclaimer, not a diagnosis claim.)
UNSAFE_LANGUAGE = re.compile(
    r"\b(diagnos\w*|pesticid\w*|fungicid\w*|insecticid\w*|herbicid\w*"
    r"|spray\w*|treat\w*|cure\w*|chemical\w*|fertili[sz]\w*|urea|dap"
    r"|dose|dosage)\b",
    re.IGNORECASE,
)

# Safe vocabulary a low-quality screening result may surface.
ALLOWED_LOW_QUALITY_PREFIXES = (
    "No clear visible symptoms",
    "Rust-like marks visible",
    "Image details unclear",
)

SAFE_PAYLOAD = {
    "crop_detected": "wheat",
    "confidence": "low",
    "model_version": "wheat-vision-test",
    "visible_findings": [
        {"class": "yellowing", "detail": "upper leaves show yellow patches"},
        {"class": "rust_like_pustules", "detail": "small brown pustules on lower leaf"},
    ],
}


# --------------------------------------------------------------------- helpers
def _settings(url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _patch_model(monkeypatch, payload: dict | None = None) -> dict:
    """Route the gateway to the local plug-in point with a stub model."""
    calls = {"n": 0}

    def fake_predict(raws, intake):
        calls["n"] += len(raws)
        return dict(payload or SAFE_PAYLOAD), None

    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    monkeypatch.setattr(vision_adapter, "predict_locally", fake_predict)
    return calls


def _noisy_jpeg(width: int, height: int, quality: int = 85, seed: int = 0) -> bytes:
    """Green-ish noisy photo: passes the gate when large enough."""
    rng = np.random.default_rng(seed)
    arr = np.clip(
        np.array([70, 140, 50]) + rng.normal(0, 28, (height, width, 3)), 0, 255
    ).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _black_jpeg(size: tuple[int, int] = (700, 700)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (0, 0, 0)).save(buf, "JPEG")
    return buf.getvalue()


def _record(raw: bytes, ident: str = "img-1") -> dict:
    return {"id": ident, "read_bytes": lambda: raw}


def _run(monkeypatch, records: list[dict], payload: dict | None = None) -> tuple:
    calls = _patch_model(monkeypatch, payload)
    result = asyncio.run(
        vision_adapter.analyze_images(AID, {"crop": "wheat"}, records)
    )
    return result, calls


# ----------------------------------------------------------------------- tests
def test_96x96_photo_runs_model_with_partial_low_evidence(monkeypatch):
    result, calls = _run(monkeypatch, [_record(_noisy_jpeg(96, 96))])
    assert calls["n"] == 1, "a 96x96 decodable photo must reach the model"
    assert result.status == "partial"
    assert result.evidence_band == "low"
    assert result.data["confidence"] == "low"
    assert result.data["low_quality"] is True
    for flag in ("low_quality_image", "low_confidence", "retake_recommended"):
        assert flag in result.safety_flags


def test_200x200_compressed_photo_runs_model(monkeypatch):
    result, calls = _run(monkeypatch, [_record(_noisy_jpeg(200, 200, quality=40))])
    assert calls["n"] == 1, "a compressed 200x200 photo must reach the model"
    assert result.status == "partial"
    assert result.evidence_band == "low"
    assert result.data["confidence"] == "low"


def test_tiny_corrupt_black_images_hard_block_without_model(monkeypatch):
    cases = {
        "tiny 64x64": _noisy_jpeg(64, 64),
        "corrupt": b"not-an-image-at-all",
        "black": _black_jpeg(),
    }
    calls = _patch_model(monkeypatch)
    for label, raw in cases.items():
        result = asyncio.run(
            vision_adapter.analyze_images(AID, {"crop": "wheat"}, [_record(raw)])
        )
        assert result.status == "not_assessed", label
        assert "photo_quality_failed" in result.safety_flags, label
        assert "no_visual_analysis_performed" in result.safety_flags, label
        assert result.evidence_band == "not_calibrated", label
    assert calls["n"] == 0, "hard-blocked photos must never run the model"


def test_low_quality_result_is_never_medium_or_high_confidence(monkeypatch):
    payload = dict(SAFE_PAYLOAD, confidence="medium")
    result, calls = _run(
        monkeypatch,
        [
            _record(_noisy_jpeg(96, 96), "img-1"),
            _record(_noisy_jpeg(96, 96, seed=1), "img-2"),
        ],
        payload=payload,
    )
    assert calls["n"] == 2
    assert result.status == "partial"
    assert result.evidence_band == "low"
    assert str(result.data["confidence"]).lower() == "low"
    assert result.evidence_band not in {"medium", "high"}


def test_low_quality_result_never_uses_diagnosis_or_chemical_language(monkeypatch):
    result, _ = _run(monkeypatch, [_record(_noisy_jpeg(96, 96))])
    text = " ".join(
        [result.summary, result.evidence_reason, *result.observations, *result.checks]
        + [str(value) for value in result.data.values()]
    )
    assert not UNSAFE_LANGUAGE.search(text)
    assert all(
        obs.startswith(ALLOWED_LOW_QUALITY_PREFIXES) for obs in result.observations
    ), "low-quality screening may only surface healthy | rust-like | unclear"


def test_crop_consumes_soft_warning_as_low_evidence_photo_visible():
    vision = AgentResult(
        assessment_id=AID,
        agent_id="vision",
        status="partial",
        summary=(
            "Photo quality is limited. This is a low-confidence visible-sign "
            "screening result; retake a clearer close-up if possible."
        ),
        observations=["No clear visible symptoms: the leaf area shows no clear sign"],
        checks=["Retake a clearer close-up in daylight with the affected leaf in focus."],
        evidence_band="low",
        evidence_reason="Low-quality image: low-confidence screening only.",
        sources=[],
        provider_or_model="self-hosted",
        version="wheat-vision-test",
        created_at=datetime.now(UTC),
        safety_flags=["low_quality_image", "low_confidence", "retake_recommended"],
    )
    intake = {"crop": "wheat", "symptoms": ["yellowing"]}
    result = assess_crop(AID, intake, vision)
    # photo_visible is consumed...
    assert result.data["vision_used"] is True
    assert result.data["vision_status"] == "partial"
    # ...but never as confirmation: farmer + photo would be medium; low-quality caps it.
    assert result.evidence_band == "low"


def test_clear_photo_behavior_is_unchanged(monkeypatch):
    result, calls = _run(monkeypatch, [_record(_noisy_jpeg(800, 700))])
    assert calls["n"] == 1
    assert result.status == "complete"
    assert "low_quality_image" not in result.safety_flags
    assert "low_confidence" not in result.safety_flags
    assert result.data.get("low_quality") is None
    assert result.evidence_band in {"low", "medium"}
    assert result.summary == "Photos can describe visible signs only and cannot confirm their cause."

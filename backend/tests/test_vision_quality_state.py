"""Quality-gate state tests for the Vision Agent.

Covers the required behaviour:

* a clear, sharp, mid-brightness photo >=512x512 is `quality_state=clear` -
  no `low_quality_image` flag and no retake flag, whatever its content;
* a decodable 96x96 photo still runs inference and may be `soft_warning`;
* corrupt / <96 px / near-black photos hard-block and never run inference;
* the "low-quality photo" copy only appears when `quality_state=soft_warning`.

Regression cases reproduce the reported bug: a sharp Full-HD close-up and a
clear 512x512 photo used to be pushed into the low-quality banner by the old
gate (`MIN_SHORT_SIDE=640`, `BLUR_MIN=100` on a downscaled copy).
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageFilter

from app.agents import vision as vision_adapter
from app.services import vision_inference as vi
from app.team_agents.vision.quality import check_quality

AID = "55555555-5555-4555-8555-555555555555"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "wheat_leaves"
HEALTHY = FIXTURES / "healthy_leaf.jpg"

WHEAT_PAYLOAD = {
    "crop_detected": "wheat",
    "visible_findings": [{"class": "healthy_looking", "detail": "leaf surface looks evenly coloured"}],
    "confidence": "low",
    "confidence_reason": "single photo, uncalibrated local model",
    "model_version": "stub-model",
}


# ------------------------------------------------------------------- helpers
def _settings(url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _sharp_jpeg(width: int, height: int, mode: str = "green", seed: int = 0) -> bytes:
    """Sharp, mid-brightness synthetic photo (noise == maximally detailed)."""
    rng = np.random.default_rng(seed)
    if mode == "green":
        arr = np.clip(np.array([70, 140, 50]) + rng.normal(0, 28, (height, width, 3)), 0, 255)
    elif mode == "rgb":
        arr = rng.integers(60, 201, (height, width, 3))
    else:  # grayscale content: no crop hue at all - quality must not care
        arr = np.clip(rng.normal(128, 40, (height, width, 1)).repeat(3, axis=2), 0, 255)
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8")).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _black_jpeg(size: tuple[int, int] = (700, 700)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (0, 0, 0)).save(buf, "JPEG")
    return buf.getvalue()


def _closeup_full_hd(path: Path = HEALTHY, fraction: float = 0.25) -> bytes:
    """Tight close-up of a real leaf photo, upscaled to Full-HD and sharpened."""
    image = Image.open(path).convert("RGB")
    width, height = image.size
    crop_w, crop_h = int(width * fraction), int(height * fraction)
    left, top = (width - crop_w) // 2, (height - crop_h) // 2
    image = image.crop((left, top, left + crop_w, top + crop_h))
    image = image.resize((1920, 1080), Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _resized(path: Path, size: tuple[int, int]) -> bytes:
    image = Image.open(path).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _record(raw: bytes, ident: str = "img-1") -> dict:
    return {"id": ident, "read_bytes": lambda: raw}


def _blurred_jpeg() -> bytes:
    """Proven-blur photo: Gaussian-blurred green leaf, sharp structure gone."""
    image = Image.fromarray(
        np.clip(
            np.array([70, 140, 50]) + np.random.default_rng(3).normal(0, 28, (700, 800, 3)),
            0,
            255,
        ).astype("uint8")
    ).filter(ImageFilter.GaussianBlur(6))
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _prepare(monkeypatch, predict=None) -> list:
    """Local mode; `predict` replaces the plug-in point and records call count."""
    monkeypatch.delenv("VISION_MODEL_DIR", raising=False)
    vi._reset_loader_cache()
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    calls = {"n": 0}
    if predict == "stub":
        def fake(raws, intake):
            calls["n"] += len(raws)
            return dict(WHEAT_PAYLOAD), None
        monkeypatch.setattr(vision_adapter, "predict_locally", fake)
    elif predict == "count":
        real = vi.predict_locally
        def counting(raws, intake):
            calls["n"] += len(raws)
            return real(raws, intake)
        monkeypatch.setattr(vision_adapter, "predict_locally", counting)
    return calls


def _run(raw: bytes) -> vision_adapter.AgentResult:
    return asyncio.run(vision_adapter.analyze_images(AID, {"crop": "wheat"}, [_record(raw)]))


# --------------------------------------------------------------------- tests
def test_clear_1024_mid_brightness_sharp_photo_is_clear():
    """4. Clear >=512 px photo -> quality_state=clear, no quality copy at all."""
    for mode in ("green", "rgb", "gray"):
        raw = _sharp_jpeg(1024, 1024, mode=mode)
        verdict = check_quality(raw)
        assert verdict["quality_state"] == "clear", (mode, verdict)
        assert verdict["passed"] is True
        assert verdict["quality_reasons"] == []
        # content hints (no crop hue in a grey photo) never change the state
        assert set(verdict["issues"]) <= {"no_plant"}, (mode, verdict)
        assert verdict["hard_issues"] == []
        assert verdict["soft_issues"] == []


def test_clear_photo_gateway_has_no_low_quality_copy(monkeypatch):
    """Clear photo -> complete result, no low_quality_image, no retake flag."""
    raw = _sharp_jpeg(1024, 1024, mode="green")
    calls = _prepare(monkeypatch, predict="stub")
    result = _run(raw)

    assert calls["n"] == 1
    assert result.status == "complete"
    assert "low_quality_image" not in result.safety_flags
    assert "retake_recommended" not in result.safety_flags
    assert "low_confidence" not in result.safety_flags
    assert result.data.get("low_quality") is None
    diagnostics = result.data["diagnostics"]
    assert diagnostics["quality_state"] == "clear"
    assert diagnostics["quality_reasons"] == []
    # quality state and model confidence are separate: this run is clear and
    # still reports the (low) model confidence without any quality flag.
    assert result.data["confidence"] == "low"
    assert "limited" not in result.summary.lower()
    assert "low-quality" not in result.summary.lower()
    vision_adapter.AgentResult.model_validate(result.model_dump(mode="json"))


def test_sharp_full_hd_closeup_is_clear_and_returns_a_real_finding(monkeypatch):
    """Regression: a sharp Full-HD close-up used to be flagged low-quality."""
    raw = _closeup_full_hd()
    verdict = check_quality(raw)
    assert (verdict["width"], verdict["height"]) == (1920, 1080)
    assert verdict["quality_state"] == "clear", verdict
    assert verdict["passed"] is True

    _prepare(monkeypatch, predict="count")
    result = _run(raw)
    assert result.status == "complete"
    assert "low_quality_image" not in result.safety_flags
    assert "retake_recommended" not in result.safety_flags
    diagnostics = result.data["diagnostics"]
    assert diagnostics["quality_state"] == "clear"
    assert diagnostics["model_loaded"] is True
    assert diagnostics["raw_top_label"] == "Wheat___Healthy"
    assert diagnostics["mapped_visible_finding"] == "healthy_looking"
    assert 0.0 < diagnostics["raw_top_score"] <= 1.0
    assert any(obs.startswith("No clear visible symptoms") for obs in result.observations)


def test_clear_512x512_photo_is_clear(monkeypatch):
    """Regression: 512 px used to be forced into the low_resolution soft tier."""
    raw = _resized(HEALTHY, (512, 512))
    verdict = check_quality(raw)
    assert verdict["quality_state"] == "clear", verdict
    assert verdict["passed"] is True

    _prepare(monkeypatch, predict="count")
    result = _run(raw)
    assert result.status == "complete"
    assert "low_quality_image" not in result.safety_flags
    assert result.data["diagnostics"]["quality_state"] == "clear"
    # The fixture is a wheat ear/head shot (see fixtures README), so leaf
    # screening is out of scope and the public app-safe finding is "unclear";
    # the raw label stays in diagnostics as technical data only.
    assert result.data["diagnostics"]["raw_top_label"] == "Wheat___Healthy"
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert result.data["photo_subject"] == "wheat_ear_or_head"
    assert result.data["screening_scope"] == "leaf_screening_not_applicable"


def test_96x96_photo_runs_inference_with_soft_warning(monkeypatch):
    """5. A decodable 96x96 photo still reaches the model."""
    raw = _sharp_jpeg(96, 96)
    verdict = check_quality(raw)
    assert verdict["quality_state"] == "soft_warning", verdict
    assert verdict["hard_issues"] == []
    assert "low_resolution" in verdict["soft_issues"]

    calls = _prepare(monkeypatch, predict="stub")
    result = _run(raw)
    assert calls["n"] == 1, "a 96x96 decodable photo must reach the model"
    assert result.status == "partial"
    assert result.data["low_quality"] is True
    assert "low_quality_image" in result.safety_flags
    diagnostics = result.data["diagnostics"]
    assert diagnostics["quality_state"] == "soft_warning"
    assert diagnostics["quality_reasons"] == ["low_resolution"]
    # the ONNX session really ran for this photo
    assert diagnostics["model_loaded"] is True
    assert diagnostics["preprocess_shape"] == [3, 224, 224]
    assert isinstance(diagnostics["raw_top_index"], int)
    # ...and only now does the low-quality copy appear
    assert "limited" in result.summary.lower()


def test_soft_warning_never_prevents_inference(monkeypatch):
    """Any decodable >=96 px photo with only soft issues still runs the model."""
    soft_cases = {
        "96x96": _sharp_jpeg(96, 96),
        "320x240": _sharp_jpeg(320, 240),
        "proven blur 800x700": _blurred_jpeg(),
    }
    for label, raw in soft_cases.items():
        verdict = check_quality(raw)
        assert verdict["quality_state"] == "soft_warning", (label, verdict)
        assert verdict["hard_issues"] == [], label
        calls = _prepare(monkeypatch, predict="stub")
        result = _run(raw)
        assert calls["n"] == 1, label
        assert result.status == "partial", label
        assert result.data["diagnostics"]["quality_state"] == "soft_warning", label


def test_corrupt_tiny_and_near_black_hard_block_without_inference(monkeypatch):
    """6. Only corrupt / unreadable / <96 px / near-black hard-block."""
    cases = {
        "corrupt": b"not-an-image-at-all",
        "tiny 64x64": _sharp_jpeg(64, 64),
        "near-black": _black_jpeg(),
    }
    for label, raw in cases.items():
        verdict = check_quality(raw)
        assert verdict["quality_state"] == "blocked", (label, verdict)
        assert verdict["hard_issues"], label
        assert verdict["passed"] is False, label

        calls = _prepare(monkeypatch, predict="stub")
        result = _run(raw)
        assert calls["n"] == 0, f"{label}: inference must not run"
        assert result.status == "not_assessed", label
        assert "photo_quality_failed" in result.safety_flags, label
        assert "no_visual_analysis_performed" in result.safety_flags, label
        diagnostics = result.data["diagnostics"]
        assert diagnostics["quality_state"] == "blocked", label
        assert diagnostics["model_loaded"] is False, label
        assert diagnostics["raw_top_index"] is None, label
        assert diagnostics["mapped_visible_finding"] is None, label


def test_no_plant_is_reported_but_never_gates():
    """Content hints stay informational: hard blocks are limited to the spec's."""
    gray = _sharp_jpeg(800, 700, mode="gray")
    verdict = check_quality(gray)
    assert "no_plant" in verdict["issues"], verdict
    assert verdict["quality_state"] == "clear", verdict
    assert verdict["passed"] is True
    assert "no_plant" not in verdict["quality_reasons"]


def test_low_quality_copy_only_when_quality_state_is_soft_warning(monkeypatch):
    """The gateway never adds the low-quality copy for a clear photo."""
    # soft -> copy present
    _prepare(monkeypatch, predict="stub")
    soft_result = _run(_sharp_jpeg(96, 96))
    assert soft_result.data["diagnostics"]["quality_state"] == "soft_warning"
    assert "Photo quality is limited" in soft_result.summary
    assert "retake" in " ".join(soft_result.checks).lower()

    # clear -> copy absent
    _prepare(monkeypatch, predict="stub")
    clear_result = _run(_sharp_jpeg(1024, 1024))
    assert clear_result.data["diagnostics"]["quality_state"] == "clear"
    assert "Photo quality is limited" not in clear_result.summary
    assert "retake_recommended" not in clear_result.safety_flags

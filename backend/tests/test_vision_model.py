"""Tests for the shipped local Vision model (ONNX, self-hosted, no cloud API).

Covers the task requirements: artifacts exist and load, ``predict_locally``
returns a valid contract payload, healthy fixtures map to ``healthy_looking``,
rust fixtures map to ``rust_like_pustules``, corrupt input abstains,
confidence never exceeds ``medium``, output passes the gateway's
``_accept_prediction`` fail-closed validator, the Crop Agent consumes the
Vision result, non-wheat output is rejected by the scope gate, and missing
artifacts still fall back to ``(None, reason)``.

Fixtures are real, CC-licensed wheat leaf photos from iNaturalist, stored in
``tests/fixtures/wheat_leaves/`` with full attribution (see its README.md).
They were selected by visually verifying the photo AND observing the model's
own prediction on it - no fabricated or synthetic findings.
"""

from __future__ import annotations

import asyncio
import io
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
from PIL import Image

from app.agents import vision as vision_adapter
from app.agents.crop import assess_crop
from app.schemas import AgentResult
from app.services import vision_inference as vi
from app.services.vision_inference import MISSING_ARTIFACTS_REASON, predict_locally
from app.team_agents.vision.quality import check_quality

AID = "33333333-3333-4333-8333-333333333333"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "wheat_leaves"
HEALTHY = FIXTURES / "healthy_leaf.jpg"
BROWN_RUST = FIXTURES / "brown_rust_leaf.jpg"
YELLOW_RUST = FIXTURES / "yellow_rust_leaf.jpg"

# Chemical/product/action language that must never appear anywhere in output
# (same convention as test_vision_integration.py).
UNSAFE_PRODUCT = re.compile(
    r"\b(pesticides?|fungicides?|insecticides?|herbicides?|spray\w*|doses?|dosage|"
    r"fertili[sz]ers?|urea|dap|npk|potash)\b",
    re.IGNORECASE,
)

# Strict claim language, checked only on model-sourced strings (finding
# details, confidence reasons). Gateway/crop card text legitimately contains
# negated safety wording such as "cause not confirmed" or "not a diagnosis",
# so the full-card scan must not use this pattern.
UNSAFE_MODEL_CLAIM = re.compile(
    r"\b(diagnos\w*|confirm\w*|definit\w*|infection\w*|pathogen\w*|treat\w*)\b",
    re.IGNORECASE,
)


def _settings(url: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _intake() -> dict:
    return {
        "crop": "wheat",
        "growth_stage": "tillering",
        "symptoms": ["yellowing"],
        "symptoms_spreading": "not_sure",
        "soil_moisture": "not_sure",
        "drainage": "not_sure",
        "notes": "",
    }


def _record(path: Path, ident: str = "img-1") -> dict:
    data = path.read_bytes()
    return {"id": ident, "read_bytes": lambda: data}


def _noise_jpeg(seed: int = 42) -> bytes:
    """Green-ish synthetic photo (passes the quality gate) that does not show
    any real leaf structure - used to prove the wheat scope gate abstains."""
    rng = np.random.default_rng(seed)
    arr = np.clip(np.array([70, 140, 50]) + rng.normal(0, 28, (700, 800, 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _use_shipped_model(monkeypatch) -> None:
    monkeypatch.delenv("VISION_MODEL_DIR", raising=False)
    vi._reset_loader_cache()


# --------------------------------------------------------------------- tests
def test_model_artifacts_exist_and_load():
    required = (
        "crop_leaf_diseases_vit.onnx",
        "config.json",
        "label_map.json",
        "model_card.json",
        "preprocessor_config.json",
        "hf_config_source.json",
    )
    for name in required:
        assert (vi.DEFAULT_MODEL_DIR / name).is_file(), name

    bundle, reason = vi._ensure_bundle(vi.DEFAULT_MODEL_DIR)
    assert reason is None and bundle is not None
    assert bundle["layout"] == "NCHW"
    assert bundle["image_size"] == 224
    assert len(bundle["id2label"]) == 13
    # Only wheat classes map to visible findings; everything else abstains.
    assert bundle["label_map"] == {
        "Wheat___Healthy": "healthy_looking",
        "Wheat___Brown_Rust": "rust_like_pustules",
        "Wheat___Yellow_Rust": "rust_like_pustules",
    }
    assert bundle["model_version"] == "wheat-vision-1.0.0+onnx@72c3499e0035"


def test_fixtures_pass_the_independent_quality_gate():
    for path in (HEALTHY, BROWN_RUST, YELLOW_RUST):
        verdict = check_quality(path.read_bytes())
        assert verdict["passed"] is True, (path.name, verdict["issues"])


def test_predict_locally_returns_valid_contract_payload(monkeypatch):
    _use_shipped_model(monkeypatch)
    payload, reason = predict_locally([HEALTHY.read_bytes()], _intake())
    assert reason is None and payload is not None
    assert set(payload) == {
        "crop_detected",
        "visible_findings",
        "confidence",
        "confidence_reason",
        "model_version",
    }
    assert payload["crop_detected"] == "wheat"
    assert payload["visible_findings"], payload
    for finding in payload["visible_findings"]:
        assert finding["class"] in vi.VISIBLE_CLASSES
        assert isinstance(finding["detail"], str) and finding["detail"]
        assert not UNSAFE_MODEL_CLAIM.search(finding["detail"])
    assert payload["confidence"] in {"low", "medium"}
    assert payload["confidence"] != "high"
    assert isinstance(payload["confidence_reason"], str) and payload["confidence_reason"]
    assert not UNSAFE_MODEL_CLAIM.search(payload["confidence_reason"])
    assert not UNSAFE_PRODUCT.search(str(payload))
    assert payload["model_version"]


def test_healthy_image_maps_to_healthy_looking(monkeypatch):
    _use_shipped_model(monkeypatch)
    payload, reason = predict_locally([HEALTHY.read_bytes()], _intake())
    assert reason is None and payload is not None
    assert payload["crop_detected"] == "wheat"
    classes = {f["class"] for f in payload["visible_findings"]}
    assert classes == {"healthy_looking"}, classes


def test_rust_like_images_map_to_rust_like_pustules(monkeypatch):
    # Both real rust photos (brown/leaf rust and stripe/yellow rust - the
    # model's internal top-1 on the stripe photo is Wheat___Brown_Rust, see
    # the fixtures README) must map to the single allowed visible class.
    _use_shipped_model(monkeypatch)
    for path in (BROWN_RUST, YELLOW_RUST):
        payload, reason = predict_locally([path.read_bytes()], _intake())
        assert reason is None and payload is not None, path.name
        assert payload["crop_detected"] == "wheat", path.name
        classes = {f["class"] for f in payload["visible_findings"]}
        assert classes == {"rust_like_pustules"}, (path.name, classes)


def test_corrupt_image_returns_none_with_reason(monkeypatch):
    _use_shipped_model(monkeypatch)
    payload, reason = predict_locally([b"not an image"], _intake())
    assert payload is None
    assert reason is not None and "decoded" in reason


def test_confidence_never_exceeds_medium(monkeypatch):
    _use_shipped_model(monkeypatch)
    batches = [
        [HEALTHY.read_bytes()],
        [BROWN_RUST.read_bytes()],
        [YELLOW_RUST.read_bytes()],
        [BROWN_RUST.read_bytes(), YELLOW_RUST.read_bytes()],
        [HEALTHY.read_bytes(), BROWN_RUST.read_bytes()],
    ]
    for batch in batches:
        payload, reason = predict_locally(batch, _intake())
        assert reason is None and payload is not None
        assert payload["confidence"] in {"low", "medium"}
        assert payload["confidence"] != "high"
        assert "uncalibrated" in payload["confidence_reason"]


def test_output_passes_accept_prediction(monkeypatch):
    _use_shipped_model(monkeypatch)
    payload, reason = predict_locally([BROWN_RUST.read_bytes()], _intake())
    assert reason is None and payload is not None

    raw = BROWN_RUST.read_bytes()
    passed = [{"record": {"id": "img-1"}, "raw": raw, "quality": {"passed": True}}]
    result = vision_adapter._accept_prediction(AID, payload, passed, datetime.now(UTC))

    assert result.status == "complete"
    assert result.agent_id == "vision"
    assert result.possible_causes == []
    assert result.evidence_band in {"low", "medium"}
    assert "confidence_capped_at_medium" in result.safety_flags
    assert "not_a_diagnosis" in result.safety_flags
    assert all(
        any(obs.startswith(prefix) for prefix in ("No clear", "Rust-like", "Visible", "Image"))
        for obs in result.observations
    )
    assert not UNSAFE_PRODUCT.search(str(result.model_dump(mode="json")))
    AgentResult.model_validate(result.model_dump(mode="json"))


def test_gateway_pipeline_completes_with_local_model(monkeypatch):
    _use_shipped_model(monkeypatch)
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    result = asyncio.run(
        vision_adapter.analyze_images(AID, _intake(), [_record(BROWN_RUST)])
    )
    assert result.status in {"complete", "partial"}
    assert result.status != "not_assessed"
    assert any("Rust-like" in obs for obs in result.observations)
    assert result.data["model_version"] == "wheat-vision-1.0.0+onnx@72c3499e0035"
    AgentResult.model_validate(result.model_dump(mode="json"))


def test_crop_agent_consumes_the_vision_result(monkeypatch):
    _use_shipped_model(monkeypatch)
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    vision_result = asyncio.run(
        vision_adapter.analyze_images(AID, _intake(), [_record(HEALTHY)])
    )
    assert vision_result.status in {"complete", "partial"}

    crop_result = assess_crop(AID, _intake(), vision_result)
    assert crop_result.status == "complete"
    assert crop_result.data["vision_used"] is True
    assert crop_result.data["vision_status"] == vision_result.status
    assert any(obs.startswith("Photo visible:") for obs in crop_result.observations)
    assert not UNSAFE_PRODUCT.search(str(crop_result.model_dump(mode="json")))


def test_non_wheat_model_output_is_rejected_by_the_scope_gate(monkeypatch):
    # A photo with no leaf structure: the real model does not establish a
    # wheat class, so the payload reports not_wheat and the gateway abstains.
    _use_shipped_model(monkeypatch)
    noise = _noise_jpeg()
    payload, reason = predict_locally([noise], _intake())
    assert reason is None and payload is not None
    assert payload["crop_detected"] == "not_wheat"
    assert payload["visible_findings"] == []

    record = {"id": "img-1", "read_bytes": lambda: noise}
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    result = asyncio.run(vision_adapter.analyze_images(AID, _intake(), [record]))
    assert result.status == "unsupported"
    assert "wheat_scope_gate" in result.safety_flags
    assert result.observations == []


def test_missing_artifacts_still_abstain(monkeypatch, tmp_path):
    monkeypatch.setenv("VISION_MODEL_DIR", str(tmp_path))
    vi._reset_loader_cache()
    payload, reason = predict_locally([HEALTHY.read_bytes()], _intake())
    assert payload is None
    assert reason == MISSING_ARTIFACTS_REASON
    assert "model.onnx" in reason

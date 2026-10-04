"""Integration tests for the Vision Agent gateway (safe fallback + plug-in contract).

Covers: not_assessed when no model/endpoint is configured, the independent
quality gate, no crashes without model artifacts, Crop continuing on
not_assessed Vision, unsafe model text rejection, the medium confidence cap,
wheat-only rejection, and source honesty (no fabricated sources or claims).
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
from PIL import Image

from app.agents import vision as vision_adapter
from app.agents.crop import assess_crop
from app.core.sources import source_registry
from app.schemas import AgentResult
from app.services.vision_inference import MISSING_ARTIFACTS_REASON, predict_locally
from app.team_agents.vision.quality import check_quality

AID = "22222222-2222-4222-8222-222222222222"

# Chemical/product language that must never appear in Vision output.
UNSAFE_OUTPUT = re.compile(
    r"\b(pesticides?|fungicides?|insecticides?|herbicides?|spray\w*|doses?|dosage|"
    r"fertili[sz]ers?|urea|dap|npk|potash)\b",
    re.IGNORECASE,
)

# Verified this session: exact title, journal, authors, open access (CC BY).
VERIFIED_SYMPTOM_SOURCE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10953319/"


# --------------------------------------------------------------------- helpers
def _settings(url: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _leaf_jpeg(seed: int = 7, size: tuple[int, int] = (800, 700)) -> bytes:
    """Synthetic noisy green 'leaf' photo that passes the quality gate."""
    rng = np.random.default_rng(seed)
    arr = np.clip(np.array([70, 140, 50]) + rng.normal(0, 28, (*size[::-1], 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _dark_jpeg() -> bytes:
    arr = np.zeros((700, 700, 3), dtype="uint8") + 8
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG")
    return buf.getvalue()


def _tiny_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (45, 120, 30)).save(buf, "JPEG")
    return buf.getvalue()


def _record(data: bytes, ident: str = "img-1") -> dict:
    return {"id": ident, "read_bytes": lambda: data}


def _crop_intake() -> dict:
    return {
        "crop": "wheat",
        "growth_stage": "tillering",
        "symptoms": ["yellowing"],
        "symptoms_spreading": "not_sure",
        "soil_moisture": "not_sure",
        "drainage": "not_sure",
        "notes": "",
    }


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _fake_async_client(payload):
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            return _FakeResponse(payload)

    return _Client


def _enable_remote(monkeypatch, payload) -> None:
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings("http://127.0.0.1:9/infer"))
    monkeypatch.setattr(vision_adapter.httpx, "AsyncClient", _fake_async_client(payload))


def _dump(result: AgentResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)


def _safe_payload(**overrides) -> dict:
    payload = {
        "crop_detected": "wheat",
        "visible_findings": [{"class": "yellowing", "detail": "visible yellowing on upper leaves"}],
        "confidence": "medium",
        "confidence_reason": "fixture",
        "model_version": "fixture-model-1.0",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- tests
def test_not_assessed_when_inference_url_is_empty(monkeypatch):
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    result = asyncio.run(
        vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())])
    )
    assert result.status == "not_assessed"
    assert result.agent_id == "vision"
    assert "model_unavailable" in result.safety_flags
    assert "no_dummy_output_used" in result.safety_flags
    assert result.data["quality_passed"] is True
    assert result.data["model_integration"]["state"] == "not_available"
    assert result.data["model_integration"]["plug_in_point"] == (
        "app.services.vision_inference:predict_locally"
    )
    assert result.sources == []
    assert result.possible_causes == []
    # Valid AgentResult envelope.
    AgentResult.model_validate(result.model_dump(mode="json"))


def test_quality_gate_works_independently_of_the_model():
    good = check_quality(_leaf_jpeg())
    assert good["passed"] is True and good["issues"] == []

    dark = check_quality(_dark_jpeg())
    assert dark["passed"] is False and "too_dark" in dark["issues"]

    tiny = check_quality(_tiny_jpeg())
    assert tiny["passed"] is False and "low_resolution" in tiny["issues"]

    corrupt = check_quality(b"not an image")
    assert corrupt["passed"] is False and "bad_file" in corrupt["issues"]


def test_low_quality_image_triggers_retake_not_assessed(monkeypatch):
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    result = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), [_record(_tiny_jpeg())]))
    assert result.status == "not_assessed"
    assert result.data["quality_passed"] is False
    assert any("Retake" in check for check in result.checks)
    assert "photo_quality_failed" in result.safety_flags
    assert "no_visual_analysis_performed" in result.safety_flags


def test_no_crash_when_model_artifacts_are_missing(monkeypatch):
    # The interface itself abstains with a documented reason (no loader, no files).
    payload, reason = predict_locally([_leaf_jpeg()], _crop_intake())
    assert payload is None
    assert reason == MISSING_ARTIFACTS_REASON
    assert "model.onnx" in reason

    # The gateway never raises in the same situation, with or without photos.
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    with_photos = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())]))
    without_photos = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), []))
    assert with_photos.status == "not_assessed"
    assert without_photos.status == "not_assessed"


def test_crop_continues_when_vision_is_not_assessed(monkeypatch):
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    vision_result = asyncio.run(
        vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())])
    )
    assert vision_result.status == "not_assessed"

    crop_result = assess_crop(AID, _crop_intake(), vision_result)
    assert crop_result.status == "complete"
    assert crop_result.data["vision_used"] is False
    assert crop_result.evidence_band == "low"
    assert "visible yellowing reported by the farmer" in crop_result.observations
    assert not UNSAFE_OUTPUT.search(_dump(crop_result))


def test_unsafe_model_text_is_rejected(monkeypatch):
    _enable_remote(
        monkeypatch,
        _safe_payload(
            visible_findings=[
                {"class": "yellowing", "detail": "confirmed rust infection; spray today"}
            ]
        ),
    )
    result = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())]))
    assert result.status == "unavailable"
    assert "unsafe_model_text_rejected" in result.safety_flags
    assert "no_interpretation_accepted" in result.safety_flags
    assert result.possible_causes == []
    text = _dump(result).lower()
    assert "spray" not in text and "infection" not in text


def test_confidence_can_never_exceed_medium(monkeypatch):
    cases = [
        # (confidence payload, number of quality-passed images, expected band)
        ("high", 2, "low"),
        ("medium", 1, "low"),
        ("medium", 2, "medium"),
        ("Low", 1, "low"),
        (None, 2, "low"),
    ]
    for confidence, count, expected_band in cases:
        _enable_remote(monkeypatch, _safe_payload(confidence=confidence))
        records = [_record(_leaf_jpeg(seed=i), f"img-{i}") for i in range(count)]
        result = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), records))
        assert result.status == "complete"
        assert result.evidence_band in {"low", "medium"}
        assert result.evidence_band == expected_band, (confidence, count, result.evidence_band)
        assert "capped at medium" in result.evidence_reason
        assert "confidence_capped_at_medium" in result.safety_flags
        assert result.possible_causes == []


def test_non_wheat_crop_is_rejected_or_flagged(monkeypatch):
    _enable_remote(monkeypatch, _safe_payload(crop_detected="maize"))
    rejected = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())]))
    assert rejected.status == "unsupported"
    assert "wheat_scope_gate" in rejected.safety_flags
    assert "no_interpretation_accepted" in rejected.safety_flags
    assert rejected.observations == []
    assert rejected.possible_causes == []

    _enable_remote(monkeypatch, _safe_payload(crop_detected=None))
    missing = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())]))
    assert missing.status == "unavailable"
    assert "wheat_scope_gate" in missing.safety_flags


def test_no_fabricated_sources_or_model_claims(monkeypatch):
    # Fallback path: no sources, no URLs, no model claims.
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    fallback = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())]))
    assert fallback.sources == []
    fallback_text = _dump(fallback)
    assert "http://" not in fallback_text and "https://" not in fallback_text
    assert fallback.provider_or_model in {
        "not_configured",
        "team-vision-quality-gate; inference not configured",
        "team-vision-quality-gate",
    }

    # Accepted path: a single explicitly-unverified source without an invented URL.
    _enable_remote(monkeypatch, _safe_payload())
    accepted = asyncio.run(
        vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg()), _record(_leaf_jpeg(8), "img-2")])
    )
    assert accepted.status == "complete"
    assert len(accepted.sources) == 1
    source = accepted.sources[0]
    assert source.title == "Self-hosted KisanOS vision inference"
    assert source.source_status == "unverified"
    assert source.url is None
    assert accepted.possible_causes == []
    assert not UNSAFE_OUTPUT.search(_dump(accepted))
    AgentResult.model_validate(accepted.model_dump(mode="json"))

    # Registry: model record stays unverified; the symptom reference is the
    # one verified, live-checked source.
    entries = {e["id"]: e for e in source_registry()["entries"]}
    model_entry = entries["vision-model"]
    assert model_entry["source_status"] == "unverified" and model_entry["url"] is None
    symptom_entry = entries["vision-symptom-reference"]
    assert symptom_entry["url"] == VERIFIED_SYMPTOM_SOURCE_URL
    assert symptom_entry["source_status"] == "supporting"


def test_malformed_model_payload_abstains_instead_of_crashing(monkeypatch):
    malformed = [
        ["not", "an", "object"],                                    # top-level non-object
        {"crop_detected": "wheat", "visible_findings": "abc"},      # findings not a list
        {"crop_detected": "wheat", "visible_findings": [{"class": 7}]},  # finding not a dict
    ]
    for payload in malformed:
        _enable_remote(monkeypatch, payload)
        result = asyncio.run(vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg())]))
        assert result.status in {"unavailable", "unsupported", "complete"}
        assert result.agent_id == "vision"
        assert result.possible_causes == []
        assert not UNSAFE_OUTPUT.search(_dump(result))
        AgentResult.model_validate(result.model_dump(mode="json"))


def test_vision_output_never_contains_diagnosis_or_treatment(monkeypatch):
    _enable_remote(monkeypatch, _safe_payload())
    result = asyncio.run(
        vision_adapter.analyze_images(AID, _crop_intake(), [_record(_leaf_jpeg()), _record(_leaf_jpeg(9), "img-2")])
    )
    # Observations are prefixed with the safe label vocabulary; no causes, no products.
    assert all(obs.startswith("Visible") or obs.startswith("No clear") or obs.startswith("Rust-like") or obs.startswith("Image") for obs in result.observations)
    assert result.possible_causes == []
    assert not UNSAFE_OUTPUT.search(_dump(result))
    assert "cannot confirm their cause" in result.summary

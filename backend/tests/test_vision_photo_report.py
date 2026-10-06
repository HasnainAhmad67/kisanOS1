"""Focused tests for the Vision Agent's farmer photo screening report.

Covers the ``photo_report`` object on the Vision card:

- clear + healthy-looking mapping  -> assessable / healthy, no retake
- clear + rust-like mapping        -> assessable / rust-like, <=3 checks,
  expert-review signs, no diagnosis or product language
- soft warning (limited) photo     -> limited report with the gate's own
  farmer-safe reason and retake guidance, inference still runs
- hard-blocked photo               -> not assessable, retake guidance,
  the model never runs
- clear photo + unclear mapping    -> assessable / clear / unclear, without
  any low-quality wording
- a hard sweep over every report string for diagnosis / product language
- the frontend ships the localized "Photo screening report" panel
  (source level — the frontend has no test runner; its verification is
  ``tsc`` + ``vite build``)
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from app.agents import vision as vision_adapter
from app.services import vision_inference as vi

AID = "66666666-6666-4666-8666-666666666666"
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"

# Diagnosis / product / action language that must never appear in a report.
# ("confirm" alone is allowed: "the cause is not confirmed" is the sanctioned
# disclaimer, so only the claim "confirmed disease" is blocked.)
FORBIDDEN = re.compile(
    r"confirmed\s+disease|diagnos\w*|detected|fungicid\w*|pesticid\w*"
    r"|spray\w*|chemical\w*|\bdoses?\b|treat\w*|irrigate\s+now",
    re.IGNORECASE,
)

RETAKE_GUIDANCE = (
    "Take a clear close-up photo of one affected leaf in daylight, with the "
    "leaf filling most of the frame."
)
HEALTHY_INTERPRETATION = (
    "This photo does not show clear visible warning signs. A single photo "
    "cannot rule out problems elsewhere in the field."
)
RUST_INTERPRETATION = (
    "Rust-like visible signs may be present. The cause is not confirmed from "
    "a photo alone."
)
UNCLEAR_INTERPRETATION = (
    "Photo quality was adequate, but the visible sign could not be "
    "classified by this screening model."
)
LIMITED_INTERPRETATION = (
    "A preliminary visible-sign screening was still performed on this photo. "
    "Because the photo quality is limited, this photo cannot rule out visible "
    "signs."
)
BLOCKED_INTERPRETATION = (
    "No uploaded photo passed the photo-quality checks, so no visible-sign "
    "screening was performed."
)


# ------------------------------------------------------------------ helpers
def _settings(url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _no_local_model(monkeypatch, tmp_path) -> None:
    """Empty model dir: the local diagnostics never invent a mapped finding,
    so the report is built from the stubbed payload only."""
    monkeypatch.setenv("VISION_MODEL_DIR", str(tmp_path))
    vi._reset_loader_cache()


def _patch_model(monkeypatch, payload: dict | None = None) -> dict:
    """Route the gateway to the local plug-in point with a stub model."""
    calls = {"n": 0}

    def fake_predict(raws, intake):
        calls["n"] += len(raws)
        return dict(payload if payload is not None else _payload()), None

    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    monkeypatch.setattr(vision_adapter, "predict_locally", fake_predict)
    return calls


def _payload(**overrides) -> dict:
    payload = {
        "crop_detected": "wheat",
        "visible_findings": [
            {"class": "healthy_looking", "detail": "the leaf area looks even"}
        ],
        "confidence": "medium",
        "confidence_reason": "fixture",
        "model_version": "fixture-model-1.0",
    }
    payload.update(overrides)
    return payload


def _record(data: bytes, ident: str = "img-1") -> dict:
    return {"id": ident, "read_bytes": lambda: data}


def _leaf_jpeg(seed: int = 7, size: tuple[int, int] = (800, 700)) -> bytes:
    """Clear photo: passes the gate with no quality issue at all."""
    rng = np.random.default_rng(seed)
    arr = np.clip(
        np.array([70, 140, 50]) + rng.normal(0, 28, (*size[::-1], 3)), 0, 255
    ).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _small_jpeg() -> bytes:
    """96x96: decodable, soft low_resolution warning -> inference still runs."""
    buf = io.BytesIO()
    Image.new("RGB", (96, 96), (45, 120, 30)).save(buf, "JPEG")
    return buf.getvalue()


def _black_jpeg() -> bytes:
    """700x700 near-black: hard block -> the model never runs."""
    buf = io.BytesIO()
    Image.new("RGB", (700, 700), (0, 0, 0)).save(buf, "JPEG")
    return buf.getvalue()


def _intake() -> dict:
    return {"crop": "wheat", "growth_stage": "tillering", "symptoms": ["yellowing"]}


def _run(monkeypatch, tmp_path, raw: bytes, payload: dict | None = None) -> tuple:
    _no_local_model(monkeypatch, tmp_path)
    calls = _patch_model(monkeypatch, payload)
    result = asyncio.run(
        vision_adapter.analyze_images(AID, _intake(), [_record(raw)])
    )
    return result, calls


def _report(result) -> dict:
    report = result.data.get("photo_report")
    assert isinstance(report, dict), "the Vision card must carry a photo_report"
    return report


def _strings(value) -> list[str]:
    """Every string inside a report, nested lists/dicts included."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def _assert_safe(report: dict) -> None:
    text = " ".join(_strings(report))
    assert not FORBIDDEN.search(text), text


# ------------------------------------------------------------------- tests
def test_clear_healthy_photo_reports_an_assessable_healthy_screen(monkeypatch, tmp_path):
    result, calls = _run(monkeypatch, tmp_path, _leaf_jpeg())
    assert calls["n"] == 1
    assert result.status == "complete"

    report = _report(result)
    assert report["assessment_status"] == "assessable"
    assert report["photo_quality"] == "clear"
    assert report["photo_subject"] == "wheat_leaf"
    assert report["visible_sign_category"] == "healthy_looking"
    assert report["what_is_visible"] == [
        "Leaf surface appears generally even in colour."
    ]
    assert "No clear rust-like raised marks are visible in this photo." in report[
        "what_is_not_clearly_visible"
    ]
    assert "No large distinct spots are clearly visible in this photo." in report[
        "what_is_not_clearly_visible"
    ]
    assert report["screening_interpretation"] == HEALTHY_INTERPRETATION
    assert 0 < len(report["field_checks"]) <= 2
    assert report["retake_guidance"] is None, "a clear photo needs no retake"
    assert report["expert_review_signs"] == []
    _assert_safe(report)


def test_clear_rust_like_photo_reports_three_checks_and_expert_signs(monkeypatch, tmp_path):
    payload = _payload(
        visible_findings=[
            {"class": "rust_like_pustules", "detail": "scattered round marks on the leaf"}
        ]
    )
    result, calls = _run(monkeypatch, tmp_path, _leaf_jpeg(seed=11), payload)
    assert calls["n"] == 1
    assert result.status == "complete"

    report = _report(result)
    assert report["assessment_status"] == "assessable"
    assert report["photo_quality"] == "clear"
    assert report["photo_subject"] == "wheat_leaf"
    assert report["visible_sign_category"] == "rust_like_marks"
    assert report["what_is_visible"] == [
        "Scattered orange-brown round marks are visible on the leaf surface."
    ]
    assert report["screening_interpretation"] == RUST_INTERPRETATION
    assert report["retake_guidance"] is None

    checks = report["field_checks"]
    assert len(checks) <= 3, checks
    assert checks[0] == (
        "Inspect both sides of 5–10 affected leaves for raised orange, "
        "yellow, or brown marks."
    )
    assert checks[1] == "Compare affected plants with nearby healthy-looking plants."
    assert checks[2] == "Check whether newer leaves are becoming affected."

    assert report["expert_review_signs"] == [
        "Marks spread quickly",
        "New leaves become affected",
        "A larger part of the field is affected",
    ]
    _assert_safe(report)


def test_soft_warning_photo_is_limited_with_a_reason_and_retake(monkeypatch, tmp_path):
    result, calls = _run(monkeypatch, tmp_path, _small_jpeg())
    assert calls["n"] == 1, "a soft warning never prevents the screening run"
    assert result.status == "partial"

    report = _report(result)
    assert report["assessment_status"] == "limited"
    assert report["photo_quality"] == "limited"
    # The exact reason the photo is limited, in the quality gate's own words.
    assert "The photo is too small. Please take it with the normal camera at full quality." in report[
        "what_is_not_clearly_visible"
    ]
    assert report["screening_interpretation"] == LIMITED_INTERPRETATION
    assert report["retake_guidance"] == RETAKE_GUIDANCE
    # A limited photo never claims that signs are absent.
    assert "No clear rust-like raised marks are visible in this photo." not in report[
        "what_is_not_clearly_visible"
    ]
    _assert_safe(report)


def test_hard_blocked_photo_is_not_assessable_and_never_runs_the_model(monkeypatch, tmp_path):
    result, calls = _run(monkeypatch, tmp_path, _black_jpeg())
    assert calls["n"] == 0, "a hard-blocked photo must never reach the model"
    assert result.status == "not_assessed"

    report = _report(result)
    assert report["assessment_status"] == "not_assessable"
    assert report["photo_quality"] == "unusable"
    assert report["what_is_visible"] == [], "no visible finding may be claimed"
    assert report["retake_guidance"] == RETAKE_GUIDANCE
    assert report["screening_interpretation"] == BLOCKED_INTERPRETATION
    assert any(
        "too dark" in reason for reason in report["what_is_not_clearly_visible"]
    ), report["what_is_not_clearly_visible"]
    _assert_safe(report)


def test_unclear_model_result_on_a_clear_photo_is_not_called_low_quality(monkeypatch, tmp_path):
    payload = _payload(
        visible_findings=[{"class": "unclear", "detail": "the leaf details do not separate"}]
    )
    result, calls = _run(monkeypatch, tmp_path, _leaf_jpeg(seed=13), payload)
    assert calls["n"] == 1

    report = _report(result)
    assert report["assessment_status"] == "assessable"
    assert report["photo_quality"] == "clear"
    assert report["visible_sign_category"] == "unclear"
    # The photo is a leaf close-up, so the subject stays wheat_leaf; only the
    # model's sign was unclassifiable.
    assert report["photo_subject"] == "wheat_leaf"
    assert report["screening_scope"] == "leaf_screening_applicable"
    assert report["screening_interpretation"] == UNCLEAR_INTERPRETATION
    assert report["retake_guidance"] is None
    text = " ".join(_strings(report)).lower()
    assert "low quality" not in text and "low-quality" not in text
    _assert_safe(report)


def test_every_photo_report_string_is_free_of_diagnosis_and_product_language(monkeypatch, tmp_path):
    reports: list[dict] = []

    healthy, _ = _run(monkeypatch, tmp_path, _leaf_jpeg(seed=17))
    reports.append(_report(healthy))

    rust_payload = _payload(
        visible_findings=[
            {"class": "rust_like_pustules", "detail": "scattered round marks on the leaf"}
        ]
    )
    rust, _ = _run(monkeypatch, tmp_path, _leaf_jpeg(seed=19), rust_payload)
    reports.append(_report(rust))

    limited, _ = _run(monkeypatch, tmp_path, _small_jpeg())
    reports.append(_report(limited))

    blocked, _ = _run(monkeypatch, tmp_path, _black_jpeg())
    reports.append(_report(blocked))

    unclear_payload = _payload(
        visible_findings=[{"class": "unclear", "detail": "the leaf details do not separate"}]
    )
    unclear, _ = _run(monkeypatch, tmp_path, _leaf_jpeg(seed=23), unclear_payload)
    reports.append(_report(unclear))

    dumped = json.dumps(reports, ensure_ascii=False)
    assert not FORBIDDEN.search(dumped)
    for report in reports:
        _assert_safe(report)
        # Closed enums only — the report never exposes a raw model label.
        assert report["assessment_status"] in {
            "assessable",
            "limited",
            "not_assessable",
        }
        assert report["visible_sign_category"] in {
            "healthy_looking",
            "rust_like_marks",
            "unclear",
        }
        assert report["photo_quality"] in {"clear", "limited", "unusable"}
        assert report["photo_subject"] in {
            "wheat_leaf",
            "wheat_ear_or_head",
            "whole_field_or_distant_crop",
            "other_plant_part",
            "unclear",
        }
        assert report["screening_scope"] in {
            "leaf_screening_applicable",
            "leaf_screening_not_applicable",
            "subject_unclear",
        }
        assert isinstance(report["scope_reasons"], list) and report["scope_reasons"]
        # A leaf sign may only appear inside leaf-screening scope.
        if report["screening_scope"] != "leaf_screening_applicable":
            assert report["photo_subject"] != "wheat_leaf"
            assert report["visible_sign_category"] == "unclear"


# --------------------------------------------------------------- frontend
def test_frontend_ships_the_localized_photo_screening_report_panel():
    """The panel, its EN/UR labels and the localized report sentences are
    present in the shipped sources (frontend verification is tsc + build)."""
    panels = (FRONTEND_SRC / "components" / "ResultPanels.tsx").read_text(
        encoding="utf-8"
    )
    card = (FRONTEND_SRC / "components" / "AgentCard.tsx").read_text(encoding="utf-8")
    en = (FRONTEND_SRC / "i18n" / "en.ts").read_text(encoding="utf-8")
    ur = (FRONTEND_SRC / "i18n" / "ur.ts").read_text(encoding="utf-8")
    backend_text = (FRONTEND_SRC / "i18n" / "backendText.ts").read_text(
        encoding="utf-8"
    )
    styles = (FRONTEND_SRC / "styles" / "components.css").read_text(encoding="utf-8")

    # --- panel exists and is wired into the Vision card ------------------
    assert "PhotoScreeningReport" in panels
    assert "PhotoScreeningReport" in card
    assert "isVisionPhotoReport" in panels
    assert "isVisionPhotoReport" in card
    assert "photo_report" in panels
    for field in (
        "what_is_visible",
        "what_is_not_clearly_visible",
        "screening_interpretation",
        "field_checks",
        "retake_guidance",
        "expert_review_signs",
    ):
        assert field in panels, f"panel does not read report.{field}"

    # --- every section label exists in English and Urdu -------------------
    keys = (
        "vision.report.heading",
        "vision.report.status.assessable",
        "vision.report.status.limited",
        "vision.report.status.not_assessable",
        "vision.report.category.healthy_looking",
        "vision.report.category.rust_like_marks",
        "vision.report.category.unclear",
        "vision.report.visible",
        "vision.report.notVisible",
        "vision.report.interpretation",
        "vision.report.fieldChecks",
        "vision.report.retake",
        "vision.report.expert",
    )
    for key in keys:
        assert f'"{key}"' in en, f"missing EN key {key}"
        assert f'"{key}"' in ur, f"missing UR key {key}"

    for urdu_label in (
        "تصویر کا ابتدائی جائزہ",
        "تصویر قابلِ جانچ ہے",
        "تصویر محدود طور پر قابلِ جانچ ہے",
        "تصویر کی جانچ نہیں ہو سکی",
        "تصویر میں کیا نظر آیا",
        "تصویر میں کیا واضح نظر نہیں آیا",
        "ابتدائی تشریح",
        "کھیت میں اگلی جانچ",
        "تصویر دوبارہ کب لیں",
        "ماہر سے رابطے کی علامات",
    ):
        assert urdu_label in ur, f"missing Urdu label {urdu_label}"

    for english_label in (
        "Photo screening report",
        "The photo can be assessed",
        "The photo can be partly assessed",
        "The photo could not be assessed",
        "What is visible in the photo",
        "What is not clearly visible in the photo",
        "Preliminary interpretation",
        "Next check in the field",
        "When to retake the photo",
        "Signs that mean expert review",
    ):
        assert f'"{english_label}"' in en, f"missing English label {english_label}"

    # --- the report sentences the backend actually emits are localized ----
    for sentence in (
        RETAKE_GUIDANCE,
        HEALTHY_INTERPRETATION,
        RUST_INTERPRETATION,
        LIMITED_INTERPRETATION,
        BLOCKED_INTERPRETATION,
        UNCLEAR_INTERPRETATION,
        "Inspect both sides of 5–10 affected leaves for raised orange, yellow, or brown marks.",
        "Marks spread quickly",
    ):
        assert sentence in backend_text, f"report sentence not localized: {sentence}"

    # --- status badge colours + no technical model internals in the panel --
    for modifier in (
        "photo-report__status--ok",
        "photo-report__status--warn",
        "photo-report__status--blocked",
        "photo-report__category-chip--healthy_looking",
        "photo-report__category-chip--rust_like_marks",
    ):
        assert modifier in panels or modifier in styles, modifier
    for internal in ("raw_top", "blur_score", "brightness", "safety_flags", "onnx"):
        assert internal not in panels, f"panel exposes technical field {internal}"

"""Screening-scope tests: wheat LEAF vs wheat EAR/HEAD vs whole field.

Covers the reported bug: a clear photo of a wheat ear/head was reported as a
farmer-facing leaf-rust result ("Rust-like marks visible on the leaf
surface"). The gateway now classifies the plant part deterministically and
conservatively (PIL + numpy signals only) and only ever maps the shipped
wheat leaf classes when the photo is a leaf close-up.

- existing grain-head / wheat-ear fixture -> clear, wheat_ear_or_head,
  leaf_screening_not_applicable, unclear sign, no leaf-rust wording, no
  low_quality flag, and no rust finding reaching Crop
- mature golden ear with a rust model output (the reported bug) -> same
- the supplied ripe golden ear close-up (no green / no bright straw band)
  -> wheat_ear_or_head instead of `unclear`, clear quality, no rust mapping
- a dense ripe whole-field photo -> never an ear; every indicator of the
  ripe-ear rule is a hard gate
- valid healthy wheat-leaf photo -> wheat_leaf / applicable / healthy kept
- real rust leaf fixtures -> wheat_leaf / applicable / rust mapping kept
- clear whole-field photo -> no leaf-rust mapping, leaf close-up requested
- ambiguous / other plant photo -> no leaf-rust mapping
- no farmer-facing text contains diagnosis or product language
- the frontend ships the EN/UR scope labels (frontend check is tsc + build)
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.agents import vision as vision_adapter
from app.agents.crop import assess_crop
from app.services import vision_inference as vi

AID = "77777777-7777-4777-8777-777777777777"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "wheat_leaves"
HEALTHY = FIXTURES / "healthy_leaf.jpg"  # visually: a wheat EAR/head, not a leaf
BROWN_RUST = FIXTURES / "brown_rust_leaf.jpg"
YELLOW_RUST = FIXTURES / "yellow_rust_leaf.jpg"
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
# The clear, ripe golden ear close-up shipped with the app (the photo whose
# upload reported `unclear` / "not enough detail"), and the dense ripe
# whole-field shot that must never be called an ear.
GOLDEN_EAR_CLOSEUP = FRONTEND_SRC.parent / "public" / "images" / "wheat-closeup.jpg"
RIPE_WHOLE_FIELD = FRONTEND_SRC.parent / "public" / "images" / "hero-wheat-field.jpg"

# Diagnosis / product / action language that must never reach a farmer.
FORBIDDEN = re.compile(
    r"confirmed\s+disease|diagnos\w*|detected|fungicid\w*|pesticid\w*"
    r"|spray\w*|chemical\w*|\bdoses?\b|treat\w*|irrigate\s+now",
    re.IGNORECASE,
)
# Leaf-rust wording that must never describe a non-leaf photo.
LEAF_RUST_WORDING = re.compile(
    r"rust-like marks visible|visible on the leaf surface", re.IGNORECASE
)

EAR_WHAT_IS_VISIBLE = "A mature wheat ear/head is visible in this photo."
EAR_INTERPRETATION = "This is a clear photo of a mature wheat ear/head, not a leaf."
EAR_NOT_VISIBLE = (
    "Leaf symptoms cannot be assessed because this image does not show a "
    "close-up leaf."
)
SCOPE_RETAKE = (
    "Take a clear daylight close-up of one affected leaf, with the leaf "
    "filling most of the frame."
)
EAR_OBSERVATION = "Wheat ear/head visible in the photo; leaf-sign screening was not applied."


# ------------------------------------------------------------------ helpers
def _settings(url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _use_shipped_model(monkeypatch) -> None:
    """Real local ONNX bundle (the fixtures' recorded predictions)."""
    monkeypatch.delenv("VISION_MODEL_DIR", raising=False)
    vi._reset_loader_cache()
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))


def _no_local_model(monkeypatch, tmp_path) -> None:
    """Empty model dir: the report is built from the stubbed payload only."""
    monkeypatch.setenv("VISION_MODEL_DIR", str(tmp_path))
    vi._reset_loader_cache()


def _patch_model(monkeypatch, payload: dict) -> dict:
    calls = {"n": 0}

    def fake_predict(raws, intake):
        calls["n"] += len(raws)
        return dict(payload), None

    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    monkeypatch.setattr(vision_adapter, "predict_locally", fake_predict)
    return calls


def _payload(**overrides) -> dict:
    payload = {
        "crop_detected": "wheat",
        "visible_findings": [
            {"class": "rust_like_pustules", "detail": "orange-brown pustules on the leaf surface"}
        ],
        "confidence": "medium",
        "confidence_reason": "fixture",
        "model_version": "fixture-model-1.0",
    }
    payload.update(overrides)
    return payload


def _intake() -> dict:
    return {"crop": "wheat", "growth_stage": "tillering", "symptoms": ["yellowing"]}


def _record(data: bytes, ident: str = "img-1") -> dict:
    return {"id": ident, "read_bytes": lambda: data}


def _run(monkeypatch, tmp_path, raw: bytes, payload: dict | None = None) -> tuple:
    _no_local_model(monkeypatch, tmp_path)
    calls = _patch_model(monkeypatch, payload or _payload())
    result = asyncio.run(vision_adapter.analyze_images(AID, _intake(), [_record(raw)]))
    return result, calls


def _run_shipped(monkeypatch, path: Path):
    _use_shipped_model(monkeypatch)
    return asyncio.run(vision_adapter.analyze_images(AID, _intake(), [_record(path.read_bytes())]))


def _leaf_jpeg(seed: int = 7, size: tuple[int, int] = (800, 700)) -> bytes:
    """Clear, frame-filling green leaf photo (passes the gate cleanly)."""
    rng = np.random.default_rng(seed)
    arr = np.clip(
        np.array([70, 140, 50]) + rng.normal(0, 28, (*size[::-1], 3)), 0, 255
    ).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _ear_jpeg(seed: int = 5) -> bytes:
    """Mature golden wheat ear close-up: straw-coloured head texture."""
    rng = np.random.default_rng(seed)
    width, height = 900, 700
    base = np.clip(np.array([188, 160, 86]) + rng.normal(0, 20, (height, width, 3)), 0, 255)
    image = Image.fromarray(base.astype("uint8"))
    draw = ImageDraw.Draw(image)
    for x in range(50, width, 70):
        draw.line(
            [(x, height), (x + int(rng.integers(-30, 30)), 20)], fill=(150, 124, 60), width=10
        )
        for y in range(30, height - 40, 26):
            cx = x + int((y - height) * 0.05) + int(rng.integers(-8, 8))
            draw.ellipse([cx - 14, y - 10, cx + 14, y + 10], fill=(216, 188, 108))
    image = image.filter(ImageFilter.GaussianBlur(1.0))
    arr = np.clip(
        np.asarray(image).astype(np.float64) + rng.normal(0, 8, (height, width, 3)), 0, 255
    ).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _field_jpeg(seed: int = 9) -> bytes:
    """Clear whole-field shot: blue sky band, crop rows, bare soil."""
    rng = np.random.default_rng(seed)
    width, height = 900, 700
    arr = np.zeros((height, width, 3), dtype=np.float64)
    horizon = int(height * 0.28)
    arr[:horizon] = np.array([120, 170, 225])
    arr[horizon:] = np.array([70, 140, 55])
    for y in range(horizon, height, 44):
        arr[y : y + 12] = np.array([118, 96, 70])
    arr += rng.normal(0, 16, (height, width, 3))
    buf = io.BytesIO()
    Image.fromarray(np.clip(arr, 0, 255).astype("uint8")).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _ambiguous_jpeg(seed: int = 3) -> bytes:
    """Clear but subject-less photo: no plant colour at all."""
    rng = np.random.default_rng(seed)
    arr = np.clip(rng.normal(128, 40, (700, 800, 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _report(result) -> dict:
    report = result.data.get("photo_report")
    assert isinstance(report, dict), "the Vision card must carry a photo_report"
    return report


def _farmer_text(result) -> str:
    """Everything a farmer can read on the card (no flags, no diagnostics)."""
    return " ".join(
        [
            str(result.summary),
            " ".join(str(item) for item in result.observations),
            " ".join(str(item) for item in result.checks),
            json.dumps(_report(result), ensure_ascii=False),
        ]
    )


# ------------------------------------------------------------------- tests
def test_existing_grain_head_fixture_is_screened_as_an_ear_not_a_leaf(monkeypatch):
    """The shipped `healthy_leaf.jpg` really shows a wheat ear/head."""
    result = _run_shipped(monkeypatch, HEALTHY)
    assert result.status in {"complete", "partial"}

    assert result.data["photo_subject"] == "wheat_ear_or_head"
    assert result.data["screening_scope"] == "leaf_screening_not_applicable"
    assert result.data["scope_reasons"]

    report = _report(result)
    assert report["assessment_status"] == "assessable", "the photo itself is clear"
    assert report["photo_quality"] == "clear"
    assert report["photo_subject"] == "wheat_ear_or_head"
    assert report["screening_scope"] == "leaf_screening_not_applicable"
    assert report["visible_sign_category"] == "unclear"
    assert report["what_is_visible"] == [EAR_WHAT_IS_VISIBLE]
    assert report["what_is_not_clearly_visible"] == [EAR_NOT_VISIBLE]
    assert report["screening_interpretation"] == EAR_INTERPRETATION
    assert report["retake_guidance"] == SCOPE_RETAKE
    assert report["expert_review_signs"] == []

    text = _farmer_text(result)
    assert "rust-like marks visible on the leaf surface" not in text.lower()
    assert "Rust-like" not in text
    assert "low_quality_image" not in result.safety_flags
    assert "retake_recommended" not in result.safety_flags
    # Crop-safe public output: the wheat leaf mapping never travels.
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert result.observations == [EAR_OBSERVATION]


def test_mature_ear_with_rust_model_output_never_reports_leaf_rust(monkeypatch, tmp_path):
    """The reported bug: golden ear texture read as a leaf rust result."""
    payload = _payload(
        visible_findings=[
            {"class": "rust_like_pustules", "detail": "orange-brown pustules on the leaf surface"}
        ]
    )
    result, calls = _run(monkeypatch, tmp_path, _ear_jpeg(), payload)
    assert calls["n"] == 1
    assert result.status == "complete"

    report = _report(result)
    assert report["photo_subject"] == "wheat_ear_or_head"
    assert report["screening_scope"] == "leaf_screening_not_applicable"
    assert report["visible_sign_category"] == "unclear"
    assert report["photo_quality"] == "clear"
    assert report["what_is_visible"] == [EAR_WHAT_IS_VISIBLE]

    text = _farmer_text(result)
    assert not LEAF_RUST_WORDING.search(text), text
    assert "rust" not in text.lower(), text
    assert "leaf surface" not in text.lower(), text
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert "low_quality_image" not in result.safety_flags


def test_supplied_mature_golden_ear_closeup_is_screened_as_an_ear(monkeypatch):
    """The reported bug: a clear ripe golden ear photo came back `unclear`
    ("The photo does not show enough detail to identify the plant part").

    The frame carries no green leaf band and no bright straw band, so the
    subject must be identified from the ripe head colour instead.
    """
    assert GOLDEN_EAR_CLOSEUP.exists(), "the wheat close-up asset must ship with the app"
    result = _run_shipped(monkeypatch, GOLDEN_EAR_CLOSEUP)
    assert result.status in {"complete", "partial"}

    assert result.data["photo_subject"] == "wheat_ear_or_head"
    assert result.data["screening_scope"] == "leaf_screening_not_applicable"

    report = _report(result)
    assert report["assessment_status"] == "assessable"
    assert report["photo_quality"] == "clear"  # a clear photo is never low quality
    assert report["photo_subject"] == "wheat_ear_or_head"
    assert report["screening_scope"] == "leaf_screening_not_applicable"
    assert report["visible_sign_category"] == "unclear"
    assert report["what_is_visible"] == [EAR_WHAT_IS_VISIBLE]
    assert report["what_is_not_clearly_visible"] == [EAR_NOT_VISIBLE]
    assert report["screening_interpretation"] == EAR_INTERPRETATION
    assert report["retake_guidance"] == SCOPE_RETAKE
    assert "one affected leaf" in report["retake_guidance"]
    # It must not claim the photo lacks detail any more ...
    assert not any("detail" in reason for reason in report["scope_reasons"])
    assert "not show enough detail" not in _farmer_text(result)

    # The shipped model reports a brown-rust label for this photo: it must
    # never reach the farmer or the Crop Agent from a non-leaf photo.
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    text = _farmer_text(result)
    assert not LEAF_RUST_WORDING.search(text), text
    assert "rust" not in text.lower(), text
    assert "low_quality_image" not in result.safety_flags
    assert "retake_recommended" not in result.safety_flags


def test_ripe_whole_field_photo_is_never_reported_as_an_ear(monkeypatch, tmp_path):
    """Dense ripe-field texture must not satisfy the ear/head rule."""
    assert RIPE_WHOLE_FIELD.exists()
    result, _calls = _run(monkeypatch, tmp_path, RIPE_WHOLE_FIELD.read_bytes())

    report = _report(result)
    assert report["photo_subject"] != "wheat_ear_or_head"
    assert report["screening_scope"] in {"subject_unclear", "leaf_screening_not_applicable"}
    assert report["visible_sign_category"] == "unclear"
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert not LEAF_RUST_WORDING.search(_farmer_text(result))


def test_ear_head_rule_requires_every_conservative_indicator():
    """Each indicator of the ripe-ear rule is a hard gate: nothing is forced."""
    signals = {
        "green": 0.0,
        "straw": 0.0,
        "plant": 0.0,
        "sky_top": 0.0,
        "sky_bottom": 0.0,
        "head_ratio": 1.0,
        "coherence": 0.0,
        "ripe": 0.75,
        "ripe_coherence": 0.99,
        "defocus": 0.31,
    }
    assert vision_adapter._is_ear_closeup(signals, wheat_evidence=True, low_quality=False)
    # Not a clear photo, or wheat not established -> never an ear/head.
    assert not vision_adapter._is_ear_closeup(signals, wheat_evidence=True, low_quality=True)
    assert not vision_adapter._is_ear_closeup(signals, wheat_evidence=False, low_quality=False)
    for key, value in (
        ("ripe", 0.29),  # not enough mature head colour
        ("ripe_coherence", 0.44),  # scattered tan specks, no single object
        ("defocus", 0.19),  # dense whole-field texture
        ("green", 0.25),  # could be a green leaf close-up
        ("sky_top", 0.15),  # open sky / wider view
    ):
        variant = {**signals, key: value}
        assert not vision_adapter._is_ear_closeup(variant, True, False), key


def test_valid_healthy_leaf_closeup_keeps_the_healthy_mapping(monkeypatch, tmp_path):
    payload = _payload(
        visible_findings=[{"class": "healthy_looking", "detail": "the leaf area looks even"}]
    )
    result, calls = _run(monkeypatch, tmp_path, _leaf_jpeg(), payload)
    assert calls["n"] == 1
    assert result.status == "complete"

    assert result.data["photo_subject"] == "wheat_leaf"
    assert result.data["screening_scope"] == "leaf_screening_applicable"
    report = _report(result)
    assert report["photo_subject"] == "wheat_leaf"
    assert report["screening_scope"] == "leaf_screening_applicable"
    assert report["visible_sign_category"] == "healthy_looking"
    assert report["what_is_visible"] == ["Leaf surface appears generally even in colour."]
    assert report["retake_guidance"] is None
    assert result.data["diagnostics"]["mapped_visible_finding"] == "healthy_looking"


def test_valid_rust_leaf_fixtures_keep_the_rust_mapping(monkeypatch):
    for path in (BROWN_RUST, YELLOW_RUST):
        result = _run_shipped(monkeypatch, path)
        assert result.status in {"complete", "partial"}, path.name
        assert result.data["photo_subject"] == "wheat_leaf", path.name
        assert result.data["screening_scope"] == "leaf_screening_applicable", path.name
        assert result.data["diagnostics"]["mapped_visible_finding"] == "rust_like_pustules", path.name

        report = _report(result)
        assert report["photo_subject"] == "wheat_leaf", path.name
        assert report["screening_scope"] == "leaf_screening_applicable", path.name
        assert report["visible_sign_category"] == "rust_like_marks", path.name
        assert any("Rust-like" in obs for obs in result.observations), path.name


def test_clear_whole_field_photo_is_not_leaf_screened(monkeypatch, tmp_path):
    result, calls = _run(monkeypatch, tmp_path, _field_jpeg())
    assert calls["n"] == 1

    report = _report(result)
    assert report["photo_subject"] == "whole_field_or_distant_crop"
    assert report["screening_scope"] == "leaf_screening_not_applicable"
    assert report["visible_sign_category"] == "unclear"
    assert report["photo_quality"] == "clear"
    assert report["retake_guidance"] == SCOPE_RETAKE
    assert "one affected" in report["retake_guidance"]

    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert not LEAF_RUST_WORDING.search(_farmer_text(result))


def test_ambiguous_photo_has_no_leaf_rust_mapping(monkeypatch, tmp_path):
    result, calls = _run(monkeypatch, tmp_path, _ambiguous_jpeg())
    assert calls["n"] == 1

    report = _report(result)
    assert report["photo_subject"] == "unclear"
    assert report["screening_scope"] == "subject_unclear"
    assert report["visible_sign_category"] == "unclear"
    assert report["retake_guidance"] == SCOPE_RETAKE
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert not LEAF_RUST_WORDING.search(_farmer_text(result))


def test_other_plant_photo_is_rejected_by_the_scope_gate(monkeypatch, tmp_path):
    """A non-wheat close-up abstains and still asks for one wheat leaf."""
    payload = _payload(crop_detected="maize", visible_findings=[])
    result, _calls = _run(monkeypatch, tmp_path, _leaf_jpeg(seed=21), payload)

    assert result.status == "unsupported"
    assert result.observations == []
    assert result.data["photo_subject"] == "other_plant_part"
    assert result.data["screening_scope"] == "leaf_screening_not_applicable"
    assert any(
        "close-up" in check and "one affected leaf" in check for check in result.checks
    )


def test_crop_never_receives_a_leaf_finding_from_an_ear_photo(monkeypatch):
    """Crop integration without touching the Crop Agent: finding stays unclear."""
    vision_result = _run_shipped(monkeypatch, HEALTHY)
    crop_result = assess_crop(AID, _intake(), vision_result)

    assert crop_result.status == "complete"
    assert crop_result.data["vision_used"] is True
    assert crop_result.data["vision_finding"] == "unclear"
    photo_lines = [obs for obs in crop_result.observations if obs.startswith("Photo visible:")]
    assert photo_lines, "the ear photo still contributes a neutral photo note"
    assert not any("Rust-like" in line for line in photo_lines), photo_lines
    assert not any("leaf surface" in line.lower() for line in photo_lines), photo_lines


def test_farmer_facing_scope_output_is_free_of_diagnosis_and_product_language(
    monkeypatch, tmp_path
):
    results = []
    results.append(_run(monkeypatch, tmp_path, _ear_jpeg())[0])
    results.append(_run(monkeypatch, tmp_path, _field_jpeg())[0])
    results.append(_run(monkeypatch, tmp_path, _ambiguous_jpeg())[0])
    results.append(_run(monkeypatch, tmp_path, _leaf_jpeg())[0])
    results.append(_run_shipped(monkeypatch, HEALTHY))
    results.append(_run_shipped(monkeypatch, GOLDEN_EAR_CLOSEUP))

    for result in results:
        text = _farmer_text(result)
        assert not FORBIDDEN.search(text), text
        report = _report(result)
        assert report["assessment_status"] in {"assessable", "limited", "not_assessable"}
        assert report["visible_sign_category"] in {
            "healthy_looking",
            "rust_like_marks",
            "unclear",
        }
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
        # Invariant: a leaf sign only ever appears in leaf-screening scope.
        if report["screening_scope"] != "leaf_screening_applicable":
            assert report["visible_sign_category"] == "unclear"
            assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
            assert not LEAF_RUST_WORDING.search(text)


# --------------------------------------------------------------- frontend
def test_frontend_ships_the_plant_part_and_scope_labels():
    """Panel + EN/UR labels for the scope result (verification: tsc + build)."""
    panels = (FRONTEND_SRC / "components" / "ResultPanels.tsx").read_text(encoding="utf-8")
    en = (FRONTEND_SRC / "i18n" / "en.ts").read_text(encoding="utf-8")
    ur = (FRONTEND_SRC / "i18n" / "ur.ts").read_text(encoding="utf-8")
    backend_text = (FRONTEND_SRC / "i18n" / "backendText.ts").read_text(encoding="utf-8")

    for field in ("photo_subject", "screening_scope", "scope_reasons"):
        assert field in panels, f"panel does not read report.{field}"

    for key in (
        "vision.report.subject",
        "vision.report.scope",
        "vision.report.subject.wheat_leaf",
        "vision.report.subject.wheat_ear_or_head",
        "vision.report.subject.whole_field_or_distant_crop",
        "vision.report.subject.other_plant_part",
        "vision.report.subject.unclear",
        "vision.report.scope.leaf_screening_applicable",
        "vision.report.scope.leaf_screening_not_applicable",
        "vision.report.scope.subject_unclear",
        "vision.report.scopeNotice.ear",
    ):
        assert f'"{key}"' in en, f"missing EN key {key}"
        assert f'"{key}"' in ur, f"missing UR key {key}"

    for english in (
        "Photo subject",
        "Screening scope",
        "Wheat ear/head",
        "Leaf screening is not applicable to this image",
    ):
        assert f'"{english}"' in en, f"missing English label {english}"

    for urdu in (
        "تصویر میں نظر آنے والا حصہ",
        "اسکریننگ کی حدود",
        "گندم کا خوشہ",
        "اس تصویر پر پتے کی علامات کی اسکریننگ لاگو نہیں ہوتی",
    ):
        assert urdu in ur, f"missing Urdu label {urdu}"

    # The neutral (blue/amber, never red) scope notice for a clear ear photo.
    assert "scopeNotice" in panels

    # Backend scope sentences are localized, including the observation that
    # Crop repeats as "Photo visible: ...".
    for sentence in (
        EAR_WHAT_IS_VISIBLE,
        EAR_NOT_VISIBLE,
        EAR_INTERPRETATION,
        SCOPE_RETAKE,
        EAR_OBSERVATION,
        vision_adapter._REASON_EAR_COLOUR,
    ):
        assert sentence in backend_text, f"sentence not localized: {sentence}"

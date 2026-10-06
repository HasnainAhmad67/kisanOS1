"""Results-page consistency and demo-readiness (focused regression).

Covers the eight farmer-visible problems this pass fixes, without touching any
existing safety test:

- a clear wheat EAR/HEAD photo is reported as photo quality / photo subject /
  leaf-symptom screening - never as a primary "Unclear" - and Crop no longer
  says the photo "did not show readable details" for it
- Crop and Vision never contradict each other, and the ear/head photo is never
  mapped to a rust or disease finding
- the Farm Plan carries ONE short cross-agent observation instead of echoing
  the Vision card's own full instruction twice
- the Results input recap echoes only what was actually supplied or explicitly
  marked "not sure", never an invented value
- the optional explanation collapses to a neutral note so the Farm Plan stays
  the authoritative, visible result
- fallback states stay distinct: no photo, failed quality gate and an
  unavailable model each say something different, never fabricate a result,
  and never stop the other cards or the plan
- every new/changed farmer-facing string ships in English AND Urdu

Frontend checks are source-level (the frontend has no test runner); its
verification is ``npx tsc --noEmit`` + ``npm run build``.
"""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.agents import vision as vision_adapter
from app.agents.advisor import SAFETY_BANNER, build_farm_plan
from app.agents.crop import assess_crop
from app.schemas import AgentResult
from app.services import vision_inference as vi
from app.services.orchestrator import _input_recap

AID = "88888888-8888-4888-8888-888888888888"
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "wheat_leaves"
HEALTHY = FIXTURES / "healthy_leaf.jpg"  # visually a clear mature wheat ear/head
BROWN_RUST = FIXTURES / "brown_rust_leaf.jpg"  # a real, clear leaf close-up

# Exact farmer-facing copy required by the results-page pass.
EAR_OBSERVATION = "A mature wheat ear/head is visible in this photo."
EAR_INTERPRETATION = (
    "This is a clear photo of a mature wheat ear/head, not a leaf."
)
EAR_LIMITATION = (
    "Leaf symptoms cannot be assessed because this image does not show a "
    "close-up leaf."
)
SCOPE_RETAKE = (
    "Take a clear daylight close-up of one affected leaf, with the leaf "
    "filling most of the frame."
)
CROP_EAR_STATEMENT = (
    "A wheat ear/head is visible in the photo. The image does not show leaf "
    "symptoms for screening."
)
VISION_CROSS_CHECK = (
    "Inspect several leaves on the photographed plant and nearby plants, "
    "including both leaf surfaces, for spots, yellowing, rust-like marks, or insects."
)
RECAP_HEADING = "Your reported field information"
EXPLANATION_NOTE = (
    "Optional explanation is unavailable. The Farm Plan above remains the "
    "authoritative result."
)
UNREADABLE = "did not show readable details"
UNCLEAR_ESCALATION = "unclear or severe-looking signs"


# ------------------------------------------------------------------ helpers
def _settings(url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _use_shipped_model(monkeypatch) -> None:
    monkeypatch.delenv("VISION_MODEL_DIR", raising=False)
    vi._reset_loader_cache()
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))


def _no_local_model(monkeypatch, tmp_path) -> None:
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
            {"class": "rust_like_pustules", "detail": "orange-brown marks"}
        ],
        "confidence": "medium",
        "confidence_reason": "fixture",
        "model_version": "fixture-model-1.0",
    }
    payload.update(overrides)
    return payload


def _intake(**overrides) -> dict:
    intake = {
        "crop": "wheat",
        "growth_stage": "tillering",
        "irrigation_history": "known",
        "symptoms": ["yellowing"],
        "symptoms_spreading": "not_sure",
        "soil_moisture": "moist",
    }
    intake.update(overrides)
    return intake


def _record(data: bytes, ident: str = "img-1") -> dict:
    return {"id": ident, "read_bytes": lambda: data}


def _run(monkeypatch, tmp_path, raw: bytes, payload: dict | None = None) -> tuple:
    _no_local_model(monkeypatch, tmp_path)
    calls = _patch_model(monkeypatch, payload or _payload())
    result = asyncio.run(vision_adapter.analyze_images(AID, _intake(), [_record(raw)]))
    return result, calls


def _run_shipped(monkeypatch, path: Path) -> AgentResult:
    _use_shipped_model(monkeypatch)
    return asyncio.run(
        vision_adapter.analyze_images(AID, _intake(), [_record(path.read_bytes())])
    )


def _report(result: AgentResult) -> dict:
    report = result.data.get("photo_report")
    assert isinstance(report, dict), "the Vision card must carry a photo_report"
    return report


def _ambiguous_jpeg(seed: int = 3) -> bytes:
    """Clear but subject-less photo: no plant colour at all."""
    import numpy as np

    rng = np.random.default_rng(seed)
    arr = np.clip(rng.normal(128, 40, (700, 800, 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _tiny_jpeg(size: tuple[int, int] = (64, 64)) -> bytes:
    """Below the 96 px hard-block floor: the model must never run."""
    buf = io.BytesIO()
    Image.new("RGB", size, (118, 132, 96)).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _card(
    agent_id: str,
    *,
    status: str = "complete",
    observations: list[str] | None = None,
    checks: list[str] | None = None,
    data: dict | None = None,
    safety_flags: list[str] | None = None,
) -> AgentResult:
    return AgentResult(
        assessment_id=AID,
        agent_id=agent_id,
        status=status,
        summary=f"{agent_id.title()} card summary.",
        observations=list(observations or []),
        checks=list(checks or []),
        evidence_reason="Evidence is limited; test envelope.",
        provider_or_model="test",
        version="test",
        data=dict(data or {}),
        safety_flags=list(safety_flags or []),
    )


def _farmer_text(result: AgentResult) -> str:
    """Everything a farmer can read on the card (no flags, no diagnostics)."""
    return " ".join(
        [
            str(result.summary),
            " ".join(str(item) for item in result.observations),
            " ".join(str(item) for item in result.checks),
            json.dumps(result.data.get("photo_report") or {}, ensure_ascii=False),
        ]
    )


# -------------------------------------------------- 1. Vision ear/head status
def test_ear_photo_leads_with_quality_subject_and_scope_not_unclear(monkeypatch):
    """A clear ear/head photo never reads as a primary "Unclear" result."""
    result = _run_shipped(monkeypatch, HEALTHY)
    report = _report(result)

    # Ordered outcome: can it be read, what does it show, does leaf screening apply.
    assert report["assessment_status"] == "assessable"
    assert report["photo_quality"] == "clear"
    assert report["photo_subject"] == "wheat_ear_or_head"
    assert report["screening_scope"] == "leaf_screening_not_applicable"

    # The plain-language scope copy, not algorithmic reasoning.
    assert report["what_is_visible"] == [EAR_OBSERVATION]
    assert report["what_is_not_clearly_visible"] == [EAR_LIMITATION]
    assert report["screening_interpretation"] == EAR_INTERPRETATION
    assert report["retake_guidance"] == SCOPE_RETAKE

    # The technical status/data is preserved for audit, and the ear photo is
    # never mapped to a leaf sign.
    assert report["visible_sign_category"] == "unclear"
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert "low_quality_image" not in result.safety_flags
    assert "retake_recommended" not in result.safety_flags

    text = _farmer_text(result)
    lowered = text.lower()
    assert "rust-like marks visible" not in lowered
    assert "visible on the leaf surface" not in lowered
    for token in ("confirmed disease", "fungicide", "pesticide", "spray", "dose"):
        assert token not in lowered, token


# --------------------------------------------------- 2. Crop <-> Vision wording
def test_crop_never_calls_a_readable_ear_photo_unreadable(monkeypatch):
    """Crop states the scope, never a quality failure it did not observe."""
    vision_result = _run_shipped(monkeypatch, HEALTHY)
    crop = assess_crop(AID, _intake(symptoms=["drying"]), vision_result)

    assert crop.data["vision_finding"] == "unclear"
    assert crop.data["photo_visible_findings"] == [CROP_EAR_STATEMENT]

    everything = " ".join(
        [crop.summary, *crop.observations, *crop.checks,
         *crop.data["photo_visible_findings"]]
    )
    assert UNREADABLE not in everything
    assert "Rust-like" not in everything
    # No "the signs are unclear" escalation for a photo whose subject was read.
    assert UNCLEAR_ESCALATION not in crop.data["escalation_signs"]

    # Farmer-reported and photo-visible evidence stay separately labelled.
    assert crop.data["farmer_reported_symptoms"] == [
        "premature drying reported by the farmer"
    ]
    assert crop.data["evidence_labels"]["farmer_reported"] == crop.data[
        "farmer_reported_symptoms"
    ]
    assert crop.data["evidence_labels"]["photo_visible"] != crop.data[
        "farmer_reported_symptoms"
    ]
    # The provisional wording for farmer-reported drying is preserved exactly.
    assert "Premature drying; multiple causes possible" in crop.data[
        "crop_possibilities"
    ]


# -------------------------------------------- 3. ambiguous stays "Unclear"
def test_genuine_ambiguous_photo_stays_unclear(monkeypatch, tmp_path):
    result, _calls = _run(monkeypatch, tmp_path, _ambiguous_jpeg())
    report = _report(result)

    assert report["photo_subject"] == "unclear"
    assert report["screening_scope"] == "subject_unclear"
    assert report["visible_sign_category"] == "unclear"
    assert result.data["diagnostics"]["mapped_visible_finding"] == "unclear"
    assert "rust-like marks visible" not in _farmer_text(result).lower()


# ------------------------------------------ 4. clear leaf photo is unchanged
def test_clear_leaf_closeup_is_still_leaf_screened(monkeypatch):
    result = _run_shipped(monkeypatch, BROWN_RUST)
    report = _report(result)

    assert report["assessment_status"] == "assessable"
    assert report["photo_quality"] == "clear"
    assert report["photo_subject"] == "wheat_leaf"
    assert report["screening_scope"] == "leaf_screening_applicable"
    assert report["visible_sign_category"] == "rust_like_marks"
    assert result.data["diagnostics"]["mapped_visible_finding"] == "rust_like_pustules"


# --------------------------------------------------------- 5. no photo fallback
def test_no_photo_is_not_assessed_and_other_results_still_work(monkeypatch, tmp_path):
    _no_local_model(monkeypatch, tmp_path)
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))

    vision = asyncio.run(vision_adapter.analyze_images(AID, _intake(), []))
    assert vision.status == "not_assessed"
    assert "manual_fallback_available" in vision.safety_flags
    assert "photo_report" not in vision.data
    assert not any("rust" in str(item).lower() for item in vision.observations)

    # The other cards and the deterministic plan are unaffected.
    crop = assess_crop(AID, _intake(), vision)
    assert crop.status in {"complete", "partial"}
    plan = build_farm_plan(AID, _intake(), [crop, vision])
    assert plan.safety_banner == SAFETY_BANNER
    assert plan.checks
    assert len(plan.checks) <= 3
    assert not any(check.evidence_labels == ["vision"] for check in plan.checks)


# --------------------------------------------------- 6. failed quality gate
def test_failed_quality_gate_names_the_problem_without_any_sign(monkeypatch, tmp_path):
    result, calls = _run(monkeypatch, tmp_path, _tiny_jpeg())
    assert calls["n"] == 0, "a hard-blocked photo must never reach the model"

    assert result.status == "not_assessed"
    assert "photo_quality_failed" in result.safety_flags
    assert "no_visual_analysis_performed" in result.safety_flags
    assert any(check.startswith("Retake") for check in result.checks)
    assert result.data["diagnostics"]["mapped_visible_finding"] is None

    text = _farmer_text(result)
    lowered = text.lower()
    assert "rust-like" not in lowered
    assert "fungicide" not in lowered
    assert "pesticide" not in lowered


# --------------------------------------------------- 7. vision unavailable
def test_unavailable_vision_never_blocks_other_cards_or_the_plan(monkeypatch, tmp_path):
    _no_local_model(monkeypatch, tmp_path)
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))

    vision = asyncio.run(
        vision_adapter.analyze_images(AID, _intake(), [_record(_good_leaf())])
    )
    assert vision.status == "not_assessed"
    assert "model_unavailable" in vision.safety_flags
    assert "no_dummy_output_used" in vision.safety_flags
    # Nothing is fabricated when the model is absent.
    assert "photo_report" not in vision.data
    assert vision.observations == [
        "At least one photo passed the supplied image-quality gate."
    ]

    crop = assess_crop(AID, _intake(), vision)
    plan = build_farm_plan(AID, _intake(), [crop, vision])
    assert plan.checks
    assert not any(check.evidence_labels == ["vision"] for check in plan.checks)


def _good_leaf() -> bytes:
    """A clear, frame-filling green leaf photo (passes the quality gate)."""
    import numpy as np

    rng = np.random.default_rng(7)
    arr = np.clip(
        np.array([70, 140, 50]) + rng.normal(0, 28, (700, 800, 3)), 0, 255
    ).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


# ------------------------------------------------------- 8. Farm Plan de-dup
def test_plan_carries_one_short_vision_action_not_the_card_wording():
    from app.core.text_guard import find_unsafe

    vision = _card(
        "vision",
        status="partial",
        observations=["Image details unclear"],
        checks=[
            "Retake a clearer close-up in daylight with the affected leaf in focus.",
            "Inspect the visible pattern on several plants in the photo and note "
            "where it starts.",
        ],
    )
    crop = _card(
        "crop",
        observations=["Farmer reported yellowing on lower leaves"],
        checks=["Compare older and younger leaves"],
    )
    water = _card("water", checks=["Check soil moisture by hand at root depth"])

    plan = build_farm_plan(AID, _intake(), [crop, water, vision])
    titles = [check.title for check in plan.checks]

    assert len(titles) <= 3
    assert VISION_CROSS_CHECK in titles
    assert find_unsafe(VISION_CROSS_CHECK) == []
    # The card's own full instructions are not echoed into the plan.
    assert not any(title.startswith("Retake") for title in titles)
    vision_titles = [
        check.title for check in plan.checks if check.evidence_labels == ["vision"]
    ]
    assert vision_titles == [VISION_CROSS_CHECK]
    # Observation only: no irrigation command, no product, no diagnosis.
    for check in plan.checks:
        lowered = check.title.casefold()
        for token in ("irrigate now", "pesticide", "fertilizer", "spray", "dose"):
            assert token not in lowered, (token, check.title)


# --------------------------------------------------------- 9. input recap
def test_input_recap_echoes_every_supplied_value():
    recap = _input_recap(
        {
            "crop": "wheat",
            "area_code": "bahawalpur_sadar",
            "growth_stage": "tillering",
            "observed_at": "2026-10-01T09:30:00+05:00",
            "irrigation_history": "not_sure",
            "last_irrigation_date": None,
            "soil_moisture": "dry",
            "drainage": "poor",
            "symptom_onset": "recent",
            "symptoms_spreading": "not_sure",
            "symptoms": ["yellowing", "spots"],
            "notes": "patch near the canal",
        },
        [{"view_type": "symptom_closeup"}, {"view_type": "field_context"}],
    )

    assert recap["crop"] == "wheat"
    assert recap["area_code"] == "bahawalpur_sadar"
    assert recap["growth_stage"] == "tillering"
    assert recap["observed_at"] == "2026-10-01"
    # The farmer's own explicit unknown is kept as such - no date is invented.
    assert recap["irrigation_history"] == "not_sure"
    assert "last_irrigation_date" not in recap
    assert recap["soil_moisture"] == "dry"
    assert recap["drainage"] == "poor"
    assert recap["symptom_onset"] == "recent"
    assert recap["symptoms_spreading"] == "not_sure"
    assert recap["symptoms"] == ["yellowing", "spots"]
    assert recap["photo_count"] == 2
    assert recap["photo_views"] == ["symptom_closeup", "field_context"]
    assert recap["notes_included"] is True


def test_input_recap_never_invents_a_value_it_was_not_given():
    recap = _input_recap(
        {
            "crop": "wheat",
            "area_code": "yazman",
            "growth_stage": "not_sure",
            "irrigation_history": "known",
            "last_irrigation_date": "2026-09-20",
            "symptom_onset": "not_sure",
            "symptoms_spreading": "not_sure",
        },
        [],
    )

    # Supplied / explicitly-unknown values are kept...
    assert recap["growth_stage"] == "not_sure"
    assert recap["symptom_onset"] == "not_sure"
    assert recap["symptoms_spreading"] == "not_sure"
    assert recap["last_irrigation_date"] == "2026-09-20"
    assert recap["photo_count"] == 0

    # ...and anything the farmer never answered simply has no key at all.
    for key in (
        "observed_at",
        "soil_moisture",
        "drainage",
        "symptoms",
        "photo_views",
        "notes_included",
    ):
        if key == "notes_included":
            assert recap[key] is False
        else:
            assert key not in recap, key


# --------------------------------------------------- 10. unsupported area
def test_unsupported_area_is_stopped_with_a_clear_reason(monkeypatch):
    """A non-pilot area is rejected outright: never a silent substitution."""
    from fastapi import HTTPException

    from app.api import routes
    from app.schemas import AssessmentCreate

    monkeypatch.setattr(routes, "AREAS", {})
    payload = AssessmentCreate(
        crop="wheat",
        crop_confirmed=True,
        area_code="bahawalpur_sadar",
        area_confirmed=True,
        irrigation_history="not_sure",
        symptoms=["yellowing"],
        consent_given=True,
        consent_version="test",
    )

    with pytest.raises(HTTPException) as exc:
        routes.create_assessment(payload)

    assert exc.value.status_code == 422
    assert exc.value.detail == {
        "code": "unsupported_area",
        "message": "This area is outside configured Bahawalpur pilot coverage.",
    }


# ------------------------------------- 11. frontend wiring + EN/UR coverage
def test_frontend_renders_recap_and_collapses_the_optional_explanation():
    results_page = (FRONTEND_SRC / "pages" / "ResultsPage.tsx").read_text(
        encoding="utf-8"
    )
    panels = (FRONTEND_SRC / "components" / "ResultPanels.tsx").read_text(
        encoding="utf-8"
    )
    card = (FRONTEND_SRC / "components" / "AgentCard.tsx").read_text(encoding="utf-8")

    # Input recap: rendered near the top, before the agent cards.
    assert "<InputRecap" in results_page
    assert results_page.index("<InputRecap") < results_page.index("agent-grid")
    assert "export function InputRecap" in panels
    assert 'aria-label={t("recap.title")}' in panels

    # Optional explanation: a neutral note inside a collapsed <details>, and
    # the plan card still renders above it.
    assert 't("exp.note")' in results_page
    assert results_page.index("plan.title") < results_page.index("exp.note")
    assert 't("exp.unavailable")' not in results_page
    assert "<Card tone=" in results_page  # complete explanations stay a card

    # Fallback notes for no photo / unavailable Vision (other cards continue).
    assert "vision.noPhoto.note" in card
    assert "vision.unavailable.note" in card
    assert "manual_fallback_available" in card

    # Status order: quality -> subject -> leaf-symptom screening, and the
    # generic "Unclear" chip is hidden for a readable non-leaf photo.
    assert "vision.report.quality" in panels
    assert "vision.report.scopeShort" in panels
    assert "hideCategory" in panels
    assert 'scope !== "leaf_screening_applicable"' in panels
    # The algorithmic scope reasoning stays collapsed in Technical details.
    assert "agent-details--technical" in panels
    assert "scope_reasons" in panels


def test_all_new_farmer_facing_strings_ship_in_english_and_urdu():
    en = (FRONTEND_SRC / "i18n" / "en.ts").read_text(encoding="utf-8")
    ur = (FRONTEND_SRC / "i18n" / "ur.ts").read_text(encoding="utf-8")
    backend_text = (FRONTEND_SRC / "i18n" / "backendText.ts").read_text(
        encoding="utf-8"
    )

    keys = (
        "vision.report.quality",
        "vision.report.scopeShort",
        "vision.report.scopeShort.leaf_screening_applicable",
        "vision.report.scopeShort.leaf_screening_not_applicable",
        "vision.report.scopeShort.subject_unclear",
        "vision.noPhoto.note",
        "vision.unavailable.note",
        "exp.note",
        "recap.title",
        "recap.note",
        "recap.crop",
        "recap.area",
        "recap.observedAt",
        "recap.growthStage",
        "recap.lastIrrigation",
        "recap.soilMoisture",
        "recap.drainage",
        "recap.symptoms",
        "recap.onset",
        "recap.spreading",
        "recap.photos",
        "recap.photoViews",
        "stage.not_sure",
        "moisture.not_sure",
        "drainage.not_sure",
        "crop.wheat",
        "area.bahawalpur_sadar",
        "area.ahmadpur_east",
        "area.yazman",
        "area.hasilpur",
        "area.khairpur_tamewali",
    )
    for key in keys:
        assert f'"{key}"' in en, f"missing EN key {key}"
        assert f'"{key}"' in ur, f"missing UR key {key}"

    english = (
        "Your reported field information",
        "Photo quality",
        "Leaf-symptom screening",
        "Not applicable to this image",
        EXPLANATION_NOTE,
    )
    for sentence in english:
        assert f'"{sentence}"' in en, f"missing EN string {sentence}"

    urdu = (
        "آپ کی فراہم کردہ کھیت کی معلومات",
        "تصویر کا معیار",
        "پتے کی علامات کی اسکریننگ",
        "اس تصویر پر لاگو نہیں ہوتی",
        "اختیاری وضاحت دستیاب نہیں ہے۔ اوپر دیا گیا فارم پلان ہی حتمی نتیجہ ہے۔",
    )
    for sentence in urdu:
        assert sentence in ur, f"missing UR string {sentence}"

    # New backend sentences that must be rendered in Urdu too.
    for sentence in (CROP_EAR_STATEMENT, VISION_CROSS_CHECK):
        assert sentence in backend_text, f"sentence not localized: {sentence}"

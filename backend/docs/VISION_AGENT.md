# KisanOS Vision Agent — backend integration

**Code:** `app/agents/vision.py` (gateway, `vision-gateway-1.0.0`) · **Plug-in contract:** `app/services/vision_inference.py` · **Quality gate:** `app/team_agents/vision/quality.py` (team code, reused unchanged)
**Tests:** `tests/test_vision_integration.py`

## Execution path

```
POST /api/v1/assessments/{id}/images          quality gate runs at upload (EXIF stripped, re-encoded JPEG)
  -> DB row (quality dict stored)

POST /api/v1/assessments/{id}/analyze         (app/api/routes.py:283)
  -> orchestrator._run_job                     (app/services/orchestrator.py:198)
      -> analyze_images(assessment_id, intake, images)     [asyncio]
          1. read stored images
          2. quality gate (team check_quality)             <- works with or without any model
          3. if no quality-passed photo -> not_assessed (retake guidance)
          4a. VISION_INFERENCE_URL set   -> POST to the operator's PRIVATE endpoint
              (the only path that sends images anywhere)
          4b. VISION_INFERENCE_URL empty -> predict_locally()  <-- MODEL PLUG-IN POINT
              app.services.vision_inference.predict_locally()
              today: returns (None, reason) -> not_assessed (safe fallback)
          5. shared fail-closed validator _accept_prediction():
              wheat-only gate, class allowlist, unsafe-text rejection,
              confidence capped at medium, sources = unverified single entry
  -> Vision AgentResult -> policy_gate -> results
  -> Crop consumes Vision ONLY when status is complete/partial (else farmer symptoms only)
```

## Safe fallback (current state — no model artifacts exist)

With `VISION_INFERENCE_URL` empty and no model files, Vision answers **`not_assessed`** after the quality gate:

- quality-passed photo → `not_assessed`, flags `model_unavailable` + `no_dummy_output_used`, `data.model_integration.state = "not_available"` with the plug-in point recorded;
- failed quality → `not_assessed` with retake guidance, flags `photo_quality_failed` + `no_visual_analysis_performed`;
- no photo → `not_assessed`;
- never crashes, never invents findings, never uses the team dummy/example output, never calls Gemini/Groq (`app/team_agents/vision/llm.py` and `dummy.py` are dormant — the backend does not import them).

## Model plug-in contract (`app/services/vision_inference.py::predict_locally`)

The future loader implements `predict_locally(image_bytes, intake) -> (payload | None, reason | None)` and returns **the same payload shape the private endpoint uses**, so one validator covers both paths:

```json
{
  "crop_detected": "wheat",
  "visible_findings": [{"class": "yellowing", "detail": "..."}],
  "confidence": "low",
  "confidence_reason": "...",
  "model_version": "..."
}
```

Allowed `class` values: `healthy_looking, yellowing, rust_like_pustules, spots_or_blotches, visible_insects, drying, unclear`. `(None, reason)` whenever artifacts are missing/broken — never raise, never invent, never call a cloud API. The gateway re-validates everything regardless (defense in depth).

### Expected artifacts (missing — you provide these)

Drop location for a future integration: `backend/models/wheat_vision/` (or `$VISION_MODEL_DIR`; add a `COPY`/volume for Docker, since the image only bakes `app/`):

| File | Required | Content |
|---|---|---|
| `model.onnx` | yes | 4-D image tensor in (NCHW/NHWC, 3ch, float32/16; fixed or dynamic H×W), one score per label out |
| `label_map.json` | yes | `map` (model label → allowed class), optional `labels`, `not_wheat_labels`, `min_probability`/`medium_probability`/`secondary_probability` |
| `config.json` **or** `labels.txt` **or** `labels` in `label_map.json` | one of | model's own class names (`{"id2label": {"0": "..."}}` HF style) |
| `preprocessor_config.json` | optional | `size`, `crop_size`, `image_mean`, `image_std`, `rescale_factor` (defaults: ImageNet mean/std, rescale 1/255, 224×224; the ONNX input shape wins) |
| `model_card.json` | recommended | `name`, `url`, `publisher`, `license`, `source_status`, `retrieved_at` → becomes the card's `sources` entry |

Runtime dependency at integration time: `onnxruntime` (CPU, offline) — **not** added to `requirements.txt` yet because no loader exists.

### Candidate model status (verified by fetching its Hugging Face page only; nothing downloaded)

`Luna-Skywalker/wheat_dtect`: license **MIT**; ConvNeXT/fastai trained on the Kaggle "New Bangladeshi Crop Disease" set (healthy / yellow rust / brown rust ≈ 3 classes); ships **only `model.pkl` (115 MB pickle flagged unsafe by Hugging Face)** — no ONNX, no config/labels/preprocessor, no evaluation on the card. Using it requires a torch/fastai → ONNX export from that pickle (a supply-chain decision), authored `label_map.json`/config, and local validation on expert-labelled photos. Not integrated.

## Safety rules (enforced, tested)

- Never a confirmed disease name; observations are visible-sign descriptions only (`possible_causes` always `[]` for Vision).
- Never pesticide/fertilizer/dose/spray instructions — model text matching `UNSAFE_MODEL_TEXT` rejects the whole response (`unsafe_model_text_rejected`).
- Confidence capped at `medium` (`evidence_band` is `low`/`medium` only; `confidence_capped_at_medium` flag).
- Non-wheat or missing `crop_detected` → `unsupported`/`unavailable` (`wheat_scope_gate`), no interpretation accepted.
- Low-quality photo → `not_assessed` with retake guidance; quality gate runs independently of any model.
- Sources: fallback ships `sources=[]`; accepted output ships exactly one entry, `source_status: unverified`, no invented URL.

## Source records

- `vision-model` (registry): `unverified`, `url: null` — a deployed model still needs a real `model_card.json` + local evaluation before any stronger claim.
- `vision-symptom-reference` (registry): `supporting` — *"Classification of wheat diseases using deep learning networks with field and glasshouse images"*, Plant Pathology 2023, PMC10953319 (CC BY, John Innes Centre). URL verified live on 2026-10-04; UK/Ireland imagery, **not** Punjab-validated, and it does not validate any deployed model.
- Team contract sources `S1/S2` in `app/team_agents/vision/contract.py` remain `None` (unfilled TODO) — the backend gateway does not use that contract.

## Configuration

Active: `VISION_INFERENCE_URL`, `VISION_INFERENCE_TOKEN` (both empty in `.env.example` = safe default). Dormant by design: `GEMINI_API_KEY`/`GROQ_API_KEY`/`LLM_PROVIDER` (read only by the never-imported team `llm.py`). `VISION_MODEL_DIR` is documented for the future loader and intentionally **not** added to `config.py` (nothing reads it yet — no dead config).

## Three Vision trees (audit note)

1. `backend/app/agents/vision.py` — the only wired implementation.
2. `backend/app/team_agents/vision/` — team archive kept for traceability; backend uses only `quality.py`. Its `agent.py`/`llm.py`/`dummy.py`/`contract.py` and `test_agent.py` (not collected by pytest) implement the Gemini/Groq + dummy pipeline — **must stay unwired** (PRD: no third-party photo inference, no dummy output). Its `test_agent.py` asserts mocked Gemini/Groq/dummy paths as normal operation; harmless while dormant.
3. `agents/vision/vision/` — a newer standalone package (arrived after the original audit; untracked): quality gate → offline ONNX model (`model.py`, `check_model.py`) with `models/wheat_vision/` drop folder. All shared file names differ from the backend copy. It is **not** wired in; integrating it is a follow-up decision (it needs the same missing artifacts).

## Tests (`tests/test_vision_integration.py`)

`not_assessed` with empty endpoint · independent quality gate (pass/dark/tiny/corrupt) · retake on low quality · no crash without artifacts (`predict_locally` → `(None, reason)`) · Crop continues on `not_assessed` Vision · unsafe model text rejected · confidence never exceeds medium · non-wheat rejected/flagged · malformed payloads abstain · no fabricated sources or model claims · no diagnosis/treatment language.

Run: `python -c "import app.main"`, `pytest -q`, or `pytest tests/test_vision_integration.py -q`.

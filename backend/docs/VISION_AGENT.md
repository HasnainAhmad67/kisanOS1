# KisanOS Vision Agent — backend integration

**Code:** `app/agents/vision.py` (gateway, `vision-gateway-1.0.0`) · **Plug-in contract:** `app/services/vision_inference.py` · **Quality gate:** `app/team_agents/vision/quality.py` (team code, reused unchanged)
**Model:** `backend/models/wheat_vision/` (shipped ONNX, self-hosted CPU) · **Tests:** `tests/test_vision_integration.py` + `tests/test_vision_model.py`

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
          4b. VISION_INFERENCE_URL empty -> predict_locally()  <-- SHIPPED LOCAL MODEL
              app.services.vision_inference.predict_locally()
              lazy-loads backend/models/wheat_vision/*.onnx via onnxruntime (CPU, offline,
              ~70 ms warm); returns (None, reason) only when artifacts are missing or the
              image cannot be decoded -> not_assessed (safe fallback, never raises)
          5. shared fail-closed validator _accept_prediction():
              wheat-only gate, class allowlist, unsafe-text rejection,
              confidence capped at medium, sources = unverified single entry
  -> Vision AgentResult -> policy_gate -> results
  -> Crop consumes Vision ONLY when status is complete/partial (else farmer symptoms only)
  -> Farm Advisor contributes Vision checks/conflicts only when status is complete/partial
```

## Current state and safe fallback

With `VISION_INFERENCE_URL` empty (the default) the gateway runs the shipped local model. These paths answer **`not_assessed`** (all tested):

- artifacts missing/corrupt (e.g., `VISION_MODEL_DIR` pointed at an empty directory) → `not_assessed`, flags `model_unavailable` + `no_dummy_output_used`, `data.model_integration.state = "not_available"` with the plug-in point recorded;
- quality-passed photo but the loader abstains (undecodable image) → `not_assessed` with the abstention reason;
- failed quality → `not_assessed` with retake guidance, flags `photo_quality_failed` + `no_visual_analysis_performed`;
- no photo → `not_assessed`;
- never crashes, never invents findings, never uses the team dummy/example output, never calls Gemini/Groq (`app/team_agents/vision/llm.py` and `dummy.py` are dormant — the backend does not import them).

## Loader contract (`app/services/vision_inference.py::predict_locally`, implemented)

The loader implements `predict_locally(image_bytes, intake) -> (payload | None, reason | None)` and returns **the same payload shape the private endpoint uses**, so one validator covers both paths:

```json
{
  "crop_detected": "wheat",
  "visible_findings": [{"class": "yellowing", "detail": "..."}],
  "confidence": "low",
  "confidence_reason": "...",
  "model_version": "..."
}
```

Allowed `class` values: `healthy_looking, yellowing, rust_like_pustules, spots_or_blotches, visible_insects, drying, unclear`. Every `detail` comes from a fixed safe-text table (`DETAIL_BY_LABEL`) — the model's raw class name/text is never copied into observations. `(None, reason)` whenever artifacts are missing/broken or the image is undecodable — never raise, never invent, never call a cloud API. The gateway re-validates everything regardless (defense in depth).

### Shipped artifacts (`backend/models/wheat_vision/`, committed)

| File | Size (bytes) | Content |
|---|---|---|
| `crop_leaf_diseases_vit.onnx` | 22,301,835 | ViT-tiny **fp32** graph: input `pixel_values [N,3,224,224] float32` NCHW (mean/std 0.5, rescale 1/255), output `[N,13]` logits; sha256 `3cb2ede8723dcbcd70db7d5bb99cc0d61466c304b2c91b26f2d0d54db9fb75f3` |
| `config.json` | 967 | loader config: `model_file`, `id2label` (13 classes), preprocessing, `model_version`, source commit pin |
| `label_map.json` | 136 | 3-entry map wheat classes → visible classes; any unmapped label fails closed as `not_wheat` |
| `model_card.json` | 3,373 | provenance: publisher, license conflict, repo/commit + SHA-256 pins, fp32-not-INT8 note |
| `hf_config_source.json` | 1,428 | verbatim Hugging Face `config.json` (kept unmodified) |
| `preprocessor_config.json` | 325 | verbatim HF preprocessor (size 224, mean/std 0.5, rescale 1/255) |

`VISION_MODEL_DIR` (env, read directly by `vision_inference.py` — not `config.py`) overrides the directory; empty/absent = this default. Docker image bakes the folder (`Dockerfile`: `COPY models ./models`).

Runtime dependency: `onnxruntime>=1.20,<2` in `requirements.txt` (CPU, offline). **Windows prerequisite:** onnxruntime needs the VC++ 2019 runtime (`vcruntime140_1.dll`, `msvcp140_1.dll`) — install the Microsoft VC++ Redistributable (no pip package, no admin copy needed on Linux containers).

### Integrated model (chosen, downloaded, verified)

`wambugu71/crop_leaf_diseases_vit_onnx` (Hugging Face), file `crop_leaf_diseases_vit.onnx`, revision pinned; `model_version = wheat-vision-1.0.0+onnx@72c3499e0035`.

- **What it is:** ViT-tiny, 13 classes (wheat leaf/brown/yellow rust + healthy among them); ~70 ms warm CPU inference for two images, 0.4 s cold load.
- **Verified:** input/output/shape/dtype through onnxruntime; **zero quantization ops** → the file is **fp32, not INT8** despite the repo README's file list (recorded honestly in `model_card.json`; size ≈ 5,526,925 params × 4 B confirms). The repo's own README lists it as the pre-quantization original.
- **License conflict (recorded, unresolved):** card body says Apache-2.0, HF metadata tags `license: mit` on both the model and dataset repos. `model_card.json` states both facts; `source_status` stays `unverified` — the `sources.py` registry `vision-model` entry is intentionally untouched.
- **Known limits:** no Punjab/wheat-field validation on our side; top-1 predictions on out-of-disease-distribution photos are imperfect (each test fixture's recorded top-1 is in `tests/fixtures/wheat_leaves/README.md`). Used only for visible-sign findings; confidence derives from photo count/agreement (≥2 agreeing wheat photos → `medium`, else `low`) and is capped at medium regardless of model probability.
- Earlier candidate `Luna-Skywalker/wheat_dtect` was rejected (115 MB pickle-only artifact, no ONNX/labels/evaluation).

## Safety rules (enforced, tested)

- Never a confirmed disease name; observations are visible-sign descriptions only (`possible_causes` always `[]` for Vision).
- Model output is evidence-only: findings map through a fixed safe-text table; no diagnosis/confirmation wording can originate from the model.
- Never pesticide/fertilizer/dose/spray instructions — model text matching `UNSAFE_MODEL_TEXT` rejects the whole response (`unsafe_model_text_rejected`).
- Confidence capped at `medium` (`evidence_band` is `low`/`medium` only; `confidence_capped_at_medium` flag); `high` is structurally impossible.
- Non-wheat or missing `crop_detected` → `unsupported`/`unavailable` (`wheat_scope_gate`), no interpretation accepted.
- Low-quality photo → `not_assessed` with retake guidance; quality gate runs independently of any model.
- Sources: fallback ships `sources=[]`; accepted output ships exactly one entry from `model_card.json`, `source_status: unverified`, no invented URL.

## Source records

- `vision-model` (registry): `unverified`, `url: null` — deliberately unchanged; the shipped model's own provenance lives in `backend/models/wheat_vision/model_card.json` (with its unresolved upstream license conflict) and the accepted card carries it as its single `unverified` source entry.
- `vision-symptom-reference` (registry): `supporting` — *"Classification of wheat diseases using deep learning networks with field and glasshouse images"*, Plant Pathology 2023, PMC10953319 (CC BY, John Innes Centre). URL verified live on 2026-10-04; UK/Ireland imagery, **not** Punjab-validated, and it does not validate any deployed model.
- Team contract sources `S1/S2` in `app/team_agents/vision/contract.py` remain `None` (unfilled TODO) — the backend gateway does not use that contract.

## Configuration

Active: `VISION_INFERENCE_URL`, `VISION_INFERENCE_TOKEN` (both empty in `.env.example` = safe default); `VISION_MODEL_DIR` (read directly by `app/services/vision_inference.py`, not `config.py` — empty/absent = `backend/models/wheat_vision/`; point it at an empty directory to emulate a no-artifact deployment). `/config` reports `vision_mode`: `local_onnx_model` (default: no URL, artifacts present), `private_self_hosted` (URL set), or `quality_gate_only_no_model` (no URL, no artifacts). Dormant by design: `GEMINI_API_KEY`/`GROQ_API_KEY`/`LLM_PROVIDER` (read only by the never-imported team `llm.py`).

## Three Vision trees (audit note)

1. `backend/app/agents/vision.py` — the only wired implementation.
2. `backend/app/team_agents/vision/` — team archive kept for traceability; backend uses only `quality.py`. Its `agent.py`/`llm.py`/`dummy.py`/`contract.py` and `test_agent.py` (not collected by pytest) implement the Gemini/Groq + dummy pipeline — **must stay unwired** (PRD: no third-party photo inference, no dummy output). Its `test_agent.py` asserts mocked Gemini/Groq/dummy paths as normal operation; harmless while dormant.
3. `agents/vision/vision/` — a newer standalone package (arrived after the original audit; untracked): quality gate → offline ONNX model (`model.py`, `check_model.py`) with `models/wheat_vision/` drop folder. All shared file names differ from the backend copy. It is **not** wired in and was **not** used as the implementation source; the backend loader (`app/services/vision_inference.py`) is self-contained and ships its own artifacts under `backend/models/wheat_vision/`.

## Tests

`tests/test_vision_integration.py` (gateway, uses a temp empty `VISION_MODEL_DIR` to test abstention): `not_assessed` with empty endpoint · independent quality gate (pass/dark/tiny/corrupt) · retake on low quality · no crash without artifacts (`predict_locally` → `(None, reason)`) · Crop continues on `not_assessed` Vision · unsafe model text rejected · confidence never exceeds medium · non-wheat rejected/flagged · malformed payloads abstain · no fabricated sources or model claims · no diagnosis/treatment language.

`tests/test_vision_model.py` (real shipped model): artifacts load + contract payload shape · fixtures pass the independent quality gate · healthy fixture → `healthy_looking` · both rust fixtures → `rust_like_pustules` · corrupt image abstains · confidence never `high` (5 batch shapes) · `_accept_prediction` accepts the payload · gateway pipeline completes with the local model · Crop Agent consumes the result (`vision_used`, `Photo visible:`) · non-wheat scope gate · missing artifacts abstain. Fixtures: `tests/fixtures/wheat_leaves/` — three real CC-BY iNaturalist photos with full provenance, selection method and recorded model top-1 in that folder's `README.md`.

Run: `python -c "import app.main"`, `pytest -q` (134 tests), or `pytest tests/test_vision_model.py -q` (~9 s).

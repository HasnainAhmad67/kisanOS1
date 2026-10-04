# Vision Agent  -  kisanos/agents/vision/

Looks at a farmer's wheat photo with a **self-hosted open-source image classifier** (ONNX Runtime, CPU, offline)
and reports ONLY what is visible. It never confirms a disease, never gives chemical advice, and confidence is
capped at medium. Output = the team's MANDATORY 14-field JSON, identical to the Weather / Water / Crop / Market agents.

**No Gemini, no Groq, no cloud API, no dummy / example output.** If the model is not installed the answer is
`unavailable` (flag `model_not_available`) - the agent never invents a result.

## Flow (KisanOS)
    farmer photo (+ optional growth stage)
      1. quality gate (quality.py)      blur, brightness, resolution, plant colour, file size, pixel count
      2. self-hosted model (model.py)   photo -> resize/normalise -> ONNX Runtime -> label scores
      3. interpretation (agent.py)      model labels -> visible-sign classes via label_map.json; low score -> unclear
      4. safety sanitiser               allowed classes only, no banned words, never High confidence
      5. contract layer (contract.py)   -> 14-field JSON  (observations, possible causes, checks, evidence, sources...)
The Crop Agent / Farm Advisor read `observations`, `possible_causes`, `checks`, `evidence_band` and `safety_flags`.
When the photo fails the gate or the model is missing, status is `unavailable` and the Crop Agent uses text symptoms.

## Files
    agent.py          analyze_image() - public entry point; flow above; never raises
    model.py          ONNX Runtime loader + preprocessing + inference + model cache (this is the vision model)
    contract.py       14-field JSON builder + validator (pure Python), cause/check tables, sources
    schema.py         Pydantic model of the 14 fields (backend / local checks)      schema.json  JSON Schema
    quality.py        image-quality gate (Pillow + numpy)
    check_model.py    run it to see that the model really loads and runs, and to try your photos
    test_agent.py     23 tests         models/  where the model files go (see models/README.md)
    requirements.txt  numpy, Pillow, onnxruntime, pydantic (+ onnx for the tests)

## Use
    from agents.vision import analyze_image
    result = analyze_image(open("leaf.jpg", "rb").read(), growth_stage="tillering",
                           assessment_id="<uuid from the orchestrator, optional>")

## Setup
    pip install -r agents/vision/requirements.txt
    # then install a model - READ models/README.md (export an open-source wheat classifier to ONNX, fill 3 small JSON files)
    python -m agents.vision.check_model your_photo.jpg      # from the kisanos/ folder
Optional: VISION_MODEL_DIR=/path/to/model_folder (default: agents/vision/models/wheat_vision).

## Output (the 14 fields)
| Situation | status | evidence_band | notable safety_flags |
|---|---|---|---|
| Model analysed the photo | complete | low / medium (never high) | model_score_uncalibrated, expert_referral_recommended, crop_check_not_performed, low_model_score |
| Photo failed the quality gate | unavailable | not_calibrated | photo_quality_failed |
| Model not installed / broken | unavailable | not_calibrated | model_not_available, model_inference_failed |
| Model says "not wheat" (only if it has such a class) | unavailable | not_calibrated | non_wheat_image |
| Unexpected exception | error | not_calibrated | agent_exception |
`provider_or_model` is always `self-hosted`; `evidence_reason` names the model and the first 12 characters of its SHA-256.
`sources` is **mandatory** (never empty): the model's own entry (from model_card.json) when present, plus the symptom
reference (contract.SOURCE_REGISTRY["S1"]) in every response. Add the research-report sources there when ready.
Banned chemical / pesticide / dose words are removed and flagged `unsafe_advice_removed`.

## Test
    python -m agents.vision.test_agent       (from the kisanos/ folder)   or   python test_agent.py   (from this folder)
The tests build a small STAND-IN ONNX model (picks the class whose prototype colour is closest to the photo's mean
colour). It is a real ONNX graph run by the real onnxruntime and the real agent code, so it proves the integration
(files -> preprocessing -> inference -> findings -> 14-field JSON, offline). It does NOT prove that any wheat-disease
model recognises real diseases.

## Honest limits (read before the demo)
- **No model weights are included.** The build environment could not download any (Hugging Face and similar hosts were
  blocked), so no wheat classifier was run here. Install one (models/README.md) and judge it on 20-30 real wheat photos.
- **Scores are not probabilities of being right.** They are the model's own softmax scores; models are often over-confident
  on photos unlike their training data. The agent caps confidence at medium, reports low scores as "unclear", and says in
  `evidence_reason` that the model is unvalidated unless model_card.json sets "validated_locally": true.
- **No crop check unless the model has an "other crop" class.** A wheat-only classifier will label any plant photo as
  one of its wheat classes. The agent says so in `observations` and flags `crop_check_not_performed`; the quality gate
  only checks for plant-like colours.
- The thresholds (0.5 report, 0.75 medium, 0.2 secondary reading) and the quality thresholds are starting values -
  tune them on real photos (label_map.json / quality.py).
- A photo shows visible signs only. Rust-like findings always recommend an expert.

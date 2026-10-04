"""Plug-in contract for a future self-hosted Vision model (no model included).

This module is the single integration point where local model inference will
be added. It is called by ``app.agents.vision.analyze_images()`` after the
image quality gate passes and only when no private ``VISION_INFERENCE_URL``
is configured.

STATUS: no model loader is implemented and no model artifacts ship with this
repository, so ``predict_locally()`` always returns ``(None, reason)`` and the
gateway answers ``not_assessed`` (safe fallback). Never add dummy/example
output here: if artifacts are missing, abstain.

Expected artifacts (drop location for a future integration)::

    backend/models/wheat_vision/            (or $VISION_MODEL_DIR)
        model.onnx               REQUIRED  classifier: 4-D image tensor in,
                                            one score per label out
        label_map.json           REQUIRED  model label -> visible-sign class
        config.json              REQUIRED* {"id2label": {"0": "...", ...}}
                                            (*or labels.txt, or "labels"
                                             inside label_map.json)
        preprocessor_config.json optional  size / crop_size / image_mean /
                                            image_std / rescale_factor
        model_card.json          recommended: name, url, publisher, license,
                                            source_status, retrieved_at

Input contract (future loader):
    * quality-gate-passed JPEG bytes (EXIF already stripped at upload);
    * preprocess per preprocessor_config.json (default: ImageNet mean/std,
      rescale 1/255, 224x224, unless the ONNX graph fixes the input size);
    * CPU inference via ``onnxruntime`` (dependency to be added at
      integration time; intentionally not in requirements.txt yet).

Output contract (the same JSON payload shape the private HTTP endpoint
returns, so both paths share the fail-closed validator in
``app.agents.vision``)::

    {
      "crop_detected": "wheat" | "not_wheat",
      "visible_findings": [{"class": <one of VISIBLE_CLASSES>, "detail": "..."}],
      "confidence": "low" | "medium",        # never "high"; gateway caps it
      "confidence_reason": "...",
      "model_version": "...",
    }

Rules for the future implementation:
    * return ``(None, reason)`` when artifacts are missing or broken -
      never raise, never invent findings, never call a cloud API;
    * the gateway re-validates everything anyway (wheat-only gate, class
      allowlist, unsafe-text rejection, confidence capped at medium).
"""

from __future__ import annotations

from typing import Any

# The only visible-sign classes accepted in a payload. Kept in sync with
# app.agents.vision.ALLOWED_CLASSES; the gateway re-checks at the boundary.
VISIBLE_CLASSES = (
    "healthy_looking",
    "yellowing",
    "rust_like_pustules",
    "spots_or_blotches",
    "visible_insects",
    "drying",
    "unclear",
)

# Reason reported while no model artifacts are provided.
MISSING_ARTIFACTS_REASON = (
    "model artifacts not provided (model.onnx, label_map.json, config.json); "
    "see backend/docs/VISION_AGENT.md"
)


def predict_locally(
    image_bytes: list[bytes], intake: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Run local model inference on quality-passed images.

    Returns ``(payload, None)`` on success or ``(None, reason)`` when the
    model cannot be used. This is the implementation point for a future ONNX
    loader; today it deliberately returns ``(None, reason)`` - safe fallback,
    no placeholder output, no model file, no download, no external service.
    """
    # Future implementation: load the artifacts listed in the module
    # docstring, preprocess, run inference, map labels via label_map.json,
    # and return the documented payload - or (None, reason) on any problem.
    return None, MISSING_ARTIFACTS_REASON

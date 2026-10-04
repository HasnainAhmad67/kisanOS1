"""Local ONNX inference for the Vision Agent (self-hosted, no cloud API).

This module is the single integration point for local model inference. It is
called by ``app.agents.vision.analyze_images()`` after the image quality gate
passes and only when no private ``VISION_INFERENCE_URL`` is configured.

SHIPPED ARTIFACTS (backend/models/wheat_vision/, override with ``$VISION_MODEL_DIR``):

    crop_leaf_diseases_vit.onnx   REQUIRED  ViT-tiny-patch16-224 classifier,
                                            input [batch, 3, 224, 224] float32
                                            (NCHW), output [batch, 13] logits
    config.json                   REQUIRED  id2label + preprocessing values
                                            (image_size 224, mean/std 0.5,
                                            rescale 1/255, resample 2)
    label_map.json                REQUIRED  model label -> visible-sign class
                                            (wheat classes only)
    model_card.json               provenance: publisher, license, source
                                            status, commit + SHA-256 pins
    preprocessor_config.json      verbatim download from the base model repo
    hf_config_source.json         verbatim download of the base config.json

Input contract:
    * quality-gate-passed JPEG/PNG bytes (EXIF already stripped at upload);
    * preprocess per config.json: resize 224x224 bilinear, rescale 1/255,
      normalize with mean/std 0.5, layout NCHW (from the graph input shape);
    * CPU inference via ``onnxruntime`` (requirements.txt).

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

Rules (enforced here AND re-checked by the gateway):
    * return ``(None, reason)`` when artifacts are missing, broken, or no
      image can be decoded - never raise, never invent findings, never call a
      cloud API;
    * only labels mapped in label_map.json (wheat classes) can produce
      findings; any other model output yields ``crop_detected="not_wheat"``
      so the wheat-only scope gate abstains;
    * confidence is "medium" only when every quality-passed photo is a wheat
      class AND all photos agree on one visible class; otherwise "low";
      "high" is not a possible value;
    * finding details use plain visual language only - no diagnosis, cause,
      product, or action words (the gateway rejects unsafe model text);
    * the gateway re-validates everything anyway (wheat-only gate, class
      allowlist, unsafe-text rejection, confidence capped at medium).
"""

from __future__ import annotations

import io
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger("kisanos.vision_inference")

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

# Reason returned when artifacts are not provided (kept stable: tests and
# docs reference this exact wording).
MISSING_ARTIFACTS_REASON = (
    "model artifacts not provided (model.onnx, label_map.json, config.json); "
    "see backend/docs/VISION_AGENT.md"
)

# Default drop location (see module docstring); $VISION_MODEL_DIR overrides it
# for tests or operator-managed model directories.
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "wheat_vision"

# Plain visual descriptions per model label. Deliberately free of diagnosis,
# cause, product, or action language (gateway UNSAFE_MODEL_TEXT gate).
DETAIL_BY_LABEL: dict[str, str] = {
    "Wheat___Healthy": (
        "The leaf surface in the photo looks evenly coloured with no distinct marks."
    ),
    "Wheat___Brown_Rust": (
        "Scattered orange-brown round marks are visible on the leaf surface in the photo."
    ),
    "Wheat___Yellow_Rust": (
        "Yellow-orange streaks run along the leaf in the photo."
    ),
}


def _model_dir() -> Path:
    env = os.environ.get("VISION_MODEL_DIR", "").strip()
    return Path(env) if env else DEFAULT_MODEL_DIR


def local_model_available() -> bool:
    """True when the configured model directory holds the required artifacts.

    Cheap existence/parse check only (no ONNX session is created) so the
    public ``/config`` endpoint can report the true vision mode without
    paying model-load cost. Point ``VISION_MODEL_DIR`` at an empty directory
    to emulate a deployment without artifacts.
    """
    model_dir = _model_dir()
    try:
        config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        model_file = str(config.get("model_file") or "model.onnx")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False
    return (model_dir / model_file).is_file() and (model_dir / "label_map.json").is_file()


# ------------------------------------------------------------------ loader
# Session + parsed artifacts are loaded once and cached (thread-safe). The
# cache is keyed by model directory so tests/operators can point at another
# directory; a load failure is cached too so a broken install cannot thrash.
_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"dir": None, "bundle": None, "error": None}


def _reset_loader_cache() -> None:
    """Drop the cached session (test hook; also usable after an operator
    replaces the artifacts on disk in the same directory)."""
    with _LOCK:
        _CACHE["dir"] = None
        _CACHE["bundle"] = None
        _CACHE["error"] = None


def _load_uncached(model_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read artifacts and build the ONNX session. Returns (bundle, None) or
    (None, reason). Never raises."""
    try:
        config_path = model_dir / "config.json"
        label_path = model_dir / "label_map.json"
        if not config_path.is_file() or not label_path.is_file():
            return None, MISSING_ARTIFACTS_REASON

        config = json.loads(config_path.read_text(encoding="utf-8"))
        id2label = {int(k): str(v) for k, v in dict(config["id2label"]).items()}
        label_map = {
            str(k): str(v)
            for k, v in json.loads(label_path.read_text(encoding="utf-8")).items()
            if not str(k).startswith("_") and str(v) in VISIBLE_CLASSES
        }
        if not id2label or not label_map:
            return None, MISSING_ARTIFACTS_REASON

        model_file = str(config.get("model_file") or "model.onnx")
        model_path = model_dir / model_file
        if not model_path.is_file():
            return None, MISSING_ARTIFACTS_REASON

        version = "unknown-local-model"
        card_path = model_dir / "model_card.json"
        if card_path.is_file():
            card = json.loads(card_path.read_text(encoding="utf-8"))
            version = str(card.get("version") or version)[:80]

        import onnxruntime as ort  # local CPU runtime only; no cloud call.

        options = ort.SessionOptions()
        options.log_severity_level = 3  # errors only
        session = ort.InferenceSession(
            str(model_path), options, providers=["CPUExecutionProvider"]
        )

        # Derive layout from the graph input, not from assumptions.
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            return None, "model graph must expose exactly one input and one output; no result was used"
        shape = list(inputs[0].shape)
        if len(shape) != 4:
            return None, f"model input shape {shape} is not a 4-D image tensor; no result was used"
        if shape[1] == 3:
            layout = "NCHW"
        elif shape[3] == 3:
            layout = "HWC"
        else:
            return None, f"model input shape {shape} has no 3-channel image axis; no result was used"
        head = list(outputs[0].shape)
        if len(head) != 2 or head[1] != len(id2label):
            return None, (
                f"model output head {head} does not match the {len(id2label)}-entry label map; "
                "no result was used"
            )

        bundle = {
            "session": session,
            "input_name": inputs[0].name,
            "layout": layout,
            "id2label": id2label,
            "label_map": label_map,
            "image_size": int(config.get("image_size") or 224),
            "image_mean": [float(v) for v in config.get("image_mean") or [0.5, 0.5, 0.5]],
            "image_std": [float(v) for v in config.get("image_std") or [0.5, 0.5, 0.5]],
            "rescale": float(config.get("rescale_factor") or (1 / 255)),
            "resample": int(config.get("resample") or 2),
            "model_version": version,
        }
        return bundle, None
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("vision model artifacts rejected: %s", exc)
        return None, f"model artifacts could not be loaded ({type(exc).__name__}); no result was used"
    except Exception as exc:  # noqa: BLE001 - a broken install must abstain, not crash.
        logger.warning("vision model failed to load: %s", exc)
        return None, "model artifacts could not be loaded; no result was used"


def _ensure_bundle(model_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    key = str(model_dir)
    with _LOCK:
        if _CACHE["dir"] == key:
            return _CACHE["bundle"], _CACHE["error"]
        bundle, error = _load_uncached(model_dir)
        _CACHE["dir"] = key
        _CACHE["bundle"] = bundle
        _CACHE["error"] = error
        return bundle, error


# ------------------------------------------------------------------ image
def _preprocess(raw: bytes, bundle: dict[str, Any]) -> np.ndarray | None:
    """Decode one quality-passed image into the model's input tensor.

    Returns None when the bytes are not a decodable image (caller skips it).
    """
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image = image.convert("RGB")
            size = bundle["image_size"]
            resample = Image.Resampling(bundle["resample"])
            image = image.resize((size, size), resample)
            array = np.asarray(image, dtype=np.float32) * bundle["rescale"]
    except Exception:  # noqa: BLE001 - undecodable bytes are skipped, never fatal.
        return None
    mean = np.asarray(bundle["image_mean"], dtype=np.float32)
    std = np.asarray(bundle["image_std"], dtype=np.float32)
    array = (array - mean) / std
    if bundle["layout"] == "NCHW":
        array = array.transpose(2, 0, 1)
    return array


# ------------------------------------------------------------------ output
def _payload(
    crop_detected: str,
    findings: list[dict[str, str]],
    confidence: str,
    confidence_reason: str,
    model_version: str,
) -> dict[str, Any]:
    return {
        "crop_detected": crop_detected,
        "visible_findings": findings,
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "model_version": model_version,
    }


def predict_locally(
    image_bytes: list[bytes], intake: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Run local ONNX inference on quality-passed images.

    Returns ``(payload, None)`` on success or ``(None, reason)`` when the
    model cannot be used. Never raises, never calls a cloud API, never
    invents findings: missing/corrupt artifacts or undecodable input all
    abstain with a documented reason.
    """
    try:
        model_dir = _model_dir()
        bundle, reason = _ensure_bundle(model_dir)
        if bundle is None:
            return None, reason or MISSING_ARTIFACTS_REASON

        tensors = [t for t in (_preprocess(raw, bundle) for raw in image_bytes) if t is not None]
        if not tensors:
            return None, "no supplied photo could be decoded for local inference; no result was used"

        batch = np.stack(tensors)
        outputs = bundle["session"].run(None, {bundle["input_name"]: batch})[0]
        logits = np.asarray(outputs, dtype=np.float32)
        if logits.ndim == 1:
            logits = logits[np.newaxis, :]
        if logits.shape[1] != len(bundle["id2label"]):
            return None, "model output head does not match the label map; no result was used"

        # Numerically stable softmax over the 13 logits.
        shifted = logits - logits.max(axis=1, keepdims=True)
        probs = np.exp(shifted)
        probs /= probs.sum(axis=1, keepdims=True)

        predictions: list[tuple[str, str | None]] = []
        for row in range(logits.shape[0]):
            index = int(np.argmax(probs[row]))
            label = bundle["id2label"][index]
            predictions.append((label, bundle["label_map"].get(label)))

        wheat = [(label, visible) for label, visible in predictions if visible]
        if not wheat:
            # No wheat class established: the wheat-only gateway gate abstains.
            return _payload(
                "not_wheat", [], "low",
                "None of the quality-passed photos matched the model's wheat classes; "
                "no visible finding was produced.",
                bundle["model_version"],
            ), None

        findings: list[dict[str, str]] = []
        seen: set[str] = set()
        for label, visible in wheat:
            if visible is None:
                continue
            if visible in seen:
                continue
            seen.add(visible)
            findings.append(
                {"class": visible, "detail": DETAIL_BY_LABEL.get(label, "Visible pattern noted in the photo.")}
            )
            if len(findings) >= 4:
                break

        all_wheat = len(wheat) == len(predictions)
        agree = all_wheat and len(seen) == 1
        if agree and len(predictions) >= 2:
            confidence = "medium"
            reason_text = (
                f"All {len(predictions)} quality-passed photos matched one visible pattern; "
                "uncalibrated local model, evidence quality only."
            )
        elif agree:
            confidence = "low"
            reason_text = (
                "Only one quality-passed photo was classified; uncalibrated local model, "
                "evidence quality only."
            )
        else:
            confidence = "low"
            matched = len(wheat)
            reason_text = (
                f"Only {matched} of {len(predictions)} photos matched the wheat classes or the "
                "photos disagreed on the visible pattern; uncalibrated local model, "
                "evidence quality only."
            )

        return _payload(
            "wheat", findings, confidence, reason_text, bundle["model_version"]
        ), None
    except Exception as exc:  # noqa: BLE001 - a broken loader must never crash the pipeline.
        logger.warning("local vision inference failed: %s", exc)
        return None, f"local model inference failed ({type(exc).__name__}); no result was used"

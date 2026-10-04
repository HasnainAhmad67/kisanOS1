"""Self-hosted vision model for the KisanOS Vision Agent  (ONNX Runtime, CPU, fully offline).

No Gemini, no Groq, no other cloud API and no placeholder output: every finding comes from the
open-source image classifier whose files you put in  models/wheat_vision/  (or VISION_MODEL_DIR):

    model.onnx               the classifier (input: image tensor, output: one score per label)
    config.json              {"id2label": {"0": "healthy", "1": "yellow rust", ...}}   (Hugging Face style)
                             or labels.txt (one label per line) or "labels" inside label_map.json
    preprocessor_config.json OPTIONAL (Hugging Face style): size, crop_size, image_mean, image_std
    label_map.json           REQUIRED: maps the model's labels to the agent's visible-sign classes
    model_card.json          OPTIONAL but recommended: name, url, publisher, license, source_status ...

If any required file is missing or broken, get_model() returns (None, reason) and the agent answers
"unavailable" - it never invents a result.
"""
import hashlib
import io
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

try:
    from .contract import LABELS
except ImportError:                     # running directly from the agent folder
    from contract import LABELS

DEFAULT_DIR = Path(__file__).parent / "models" / "wheat_vision"
ALLOWED_CLASSES = set(LABELS)
IMAGENET_MEAN, IMAGENET_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
TOP_K = 5


class ModelNotAvailable(Exception):
    """The self-hosted model cannot be used (missing / broken files)."""


def model_dir() -> Path:
    return Path(os.environ.get("VISION_MODEL_DIR") or DEFAULT_DIR)


def _read_json(path: Path, required: bool):
    if not path.is_file():
        if required:
            raise ModelNotAvailable(f"{path.name} not found")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ModelNotAvailable(f"{path.name} is not valid JSON")
    if not isinstance(data, dict):
        raise ModelNotAvailable(f"{path.name} must contain a JSON object")
    return data


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


class VisionModel:
    def __init__(self, directory):
        d = Path(directory)
        onnx_path = d / "model.onnx"
        if not onnx_path.is_file():
            raise ModelNotAvailable("model.onnx not found")
        lm = _read_json(d / "label_map.json", required=True)
        cfg = _read_json(d / "config.json", required=False)
        self.pre = _read_json(d / "preprocessor_config.json", required=False) or {}
        self.card = _read_json(d / "model_card.json", required=False) or {}

        # labels
        labels = None
        if cfg and isinstance(cfg.get("id2label"), dict):
            try:
                items = sorted(((int(k), str(v)) for k, v in cfg["id2label"].items()))
                labels = [v for _, v in items]
            except ValueError:
                raise ModelNotAvailable("config.json id2label keys must be integers")
        elif (d / "labels.txt").is_file():
            labels = [ln.strip() for ln in (d / "labels.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
        elif isinstance(lm.get("labels"), list):
            labels = [str(x) for x in lm["labels"]]
        if not labels:
            raise ModelNotAvailable("no class labels found (config.json id2label, labels.txt or label_map.json labels)")
        self.labels = labels

        # label -> visible-sign class
        mp = lm.get("map")
        if not isinstance(mp, dict) or not mp:
            raise ModelNotAvailable("label_map.json needs a non-empty 'map'")
        self.mapping = {str(k).strip().lower(): str(v) for k, v in mp.items()}
        bad = sorted({v for v in self.mapping.values() if v not in ALLOWED_CLASSES})
        if bad:
            raise ModelNotAvailable(f"label_map.json maps to unknown classes: {bad}")
        self.not_wheat = {str(x).strip().lower() for x in lm.get("not_wheat_labels", [])}
        try:
            self.min_p = float(lm.get("min_probability", 0.5))
            self.medium_p = float(lm.get("medium_probability", 0.75))
            self.secondary_p = float(lm.get("secondary_probability", 0.2))
        except (TypeError, ValueError):
            raise ModelNotAvailable("label_map.json probabilities must be numbers")

        # session
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        except Exception as e:
            raise ModelNotAvailable(f"model.onnx could not be loaded ({type(e).__name__})")
        inp = self.session.get_inputs()[0]
        self.input_name, shape = inp.name, list(inp.shape)
        self.fp16 = "float16" in str(inp.type)
        if len(shape) != 4:
            raise ModelNotAvailable("model input must be a 4-D image tensor")
        self.nhwc = (shape[3] == 3 and shape[1] != 3)
        h, w = (shape[1], shape[2]) if self.nhwc else (shape[2], shape[3])
        self.static_hw = (int(h), int(w)) if isinstance(h, int) and isinstance(w, int) else None

        self.path = onnx_path
        self.sha256 = _sha256(onnx_path)
        self.mtime = datetime.fromtimestamp(onnx_path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._check_outputs()

    # ---------------------------------------------------------------- preprocessing
    def _target_sizes(self):
        """-> (resize_to, crop_to, mode). mode 'direct' = resize to (w, h); 'edge' = shortest edge then center-crop."""
        if self.static_hw:                                          # the ONNX file's own input size always wins
            h, w = self.static_hw
            return (w, h), None, "direct"
        size, crop = self.pre.get("size", 224), self.pre.get("crop_size")
        if isinstance(size, dict) and "shortest_edge" in size:
            edge = int(size["shortest_edge"])
            c = crop.get("height", edge) if isinstance(crop, dict) else crop if isinstance(crop, int) else edge
            return edge, int(c), "edge"
        if isinstance(size, dict) and "height" in size and "width" in size:
            return (int(size["width"]), int(size["height"])), None, "direct"
        return (int(size), int(size)), None, "direct"

    def preprocess(self, image_bytes: bytes) -> np.ndarray:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
        resize_to, crop_to, mode = self._target_sizes()
        if mode == "direct":
            img = img.resize(resize_to, Image.BICUBIC)
        else:
            w, h = img.size
            scale = resize_to / min(w, h)
            img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.BICUBIC)
            w, h = img.size
            left, top = (w - crop_to) // 2, (h - crop_to) // 2
            img = img.crop((left, top, left + crop_to, top + crop_to))
        arr = np.asarray(img, dtype=np.float32) * float(self.pre.get("rescale_factor", 1 / 255))
        mean = np.asarray(self.pre.get("image_mean", IMAGENET_MEAN), dtype=np.float32)
        std = np.asarray(self.pre.get("image_std", IMAGENET_STD), dtype=np.float32)
        arr = (arr - mean) / std
        if not self.nhwc:
            arr = arr.transpose(2, 0, 1)
        arr = arr[None, ...]
        return arr.astype(np.float16 if self.fp16 else np.float32)

    # ---------------------------------------------------------------- inference
    def _scores(self, tensor: np.ndarray) -> np.ndarray:
        outs = self.session.run(None, {self.input_name: tensor})
        for o in outs:                                             # pick the output that has one score per label
            o = np.asarray(o, dtype=np.float64).reshape(-1)
            if o.size == len(self.labels):
                return o
        raise ModelNotAvailable(f"model outputs do not match the {len(self.labels)} labels")

    def _check_outputs(self):
        """Warm-up run: proves the model executes and has one score per label."""
        if self.static_hw:
            h, w = self.static_hw
        else:
            resize_to, crop_to, mode = self._target_sizes()
            h, w = (crop_to, crop_to) if mode == "edge" else (resize_to[1], resize_to[0])
        shape = (1, h, w, 3) if self.nhwc else (1, 3, h, w)
        try:
            self._scores(np.zeros(shape, dtype=np.float16 if self.fp16 else np.float32))
        except ModelNotAvailable:
            raise
        except Exception as e:
            raise ModelNotAvailable(f"warm-up inference failed ({type(e).__name__})")

    def predict(self, image_bytes: bytes):
        """-> [(label, probability), ...] best first (top 5). Real inference on the given image."""
        s = self._scores(self.preprocess(image_bytes))
        probs = s if (s.min() >= 0 and abs(s.sum() - 1) < 1e-3) else _softmax(s)     # already probabilities?
        order = np.argsort(-probs)[:TOP_K]
        return [(self.labels[i], float(probs[i])) for i in order]

    def source_entry(self):
        """The model's own source object for the contract (None if model_card.json lacks name/url/publisher)."""
        c = self.card
        if not all(isinstance(c.get(k), str) and c.get(k) for k in ("name", "url", "publisher")):
            return None
        status = c.get("source_status") if c.get("source_status") in ("official", "supporting", "secondary", "unverified") else "unverified"
        return {"title": f"{c['name']} (self-hosted open-source vision model)", "url": c["url"], "publisher": c["publisher"],
                "retrieved_at": c.get("retrieved_at") if isinstance(c.get("retrieved_at"), str) else self.mtime,
                "source_status": status}

    def describe(self):
        return {"name": str(self.card.get("name") or "unnamed model"), "sha12": self.sha256[:12], "labels": len(self.labels),
                "validated_locally": bool(self.card.get("validated_locally")), "license": self.card.get("license")}


# ------------------------------------------------------------------------- cache
_LOCK = threading.Lock()
_CACHE = {}


def reset_model_cache():
    with _LOCK:
        _CACHE.clear()


def get_model():
    """-> (VisionModel, None) or (None, reason). Loads once; reloads if model.onnx changes."""
    d = model_dir()
    try:
        f = d / "model.onnx"
        key = (str(d), f.stat().st_mtime_ns if f.is_file() else None)
    except OSError:
        key = (str(d), None)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key], None
        try:
            m = VisionModel(d)
        except ModelNotAvailable as e:
            return None, str(e)
        except Exception as e:                                       # never let a loader bug escape
            return None, f"model could not be loaded ({type(e).__name__})"
        _CACHE.clear()
        _CACHE[key] = m
        return m, None

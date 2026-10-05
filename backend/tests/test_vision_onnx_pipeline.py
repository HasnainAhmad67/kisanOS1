"""Required proof for the local ONNX Vision pipeline (self-hosted, no new model).

Covers the task's required checks:

1. ONNX session metadata - input name / shape / dtype, output name / shape -
   plus the pipeline's input/output parsing (layout, normalization, label head).
2. Label lookup uses the model's *actual* id2label order from config.json
   (the order is read from the shipped file in the test, never hardcoded in
   the assertion source of truth).
3. A deterministic mocked ONNX output maps raw index -> app-safe visible finding:
   Wheat Healthy -> healthy_looking, Wheat Brown/Yellow Rust -> rust_like_pustules,
   any other / non-wheat / unknown index -> unclear.
"""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import onnxruntime as ort
import pytest
from PIL import Image

from app.agents import vision as vision_adapter
from app.services import vision_inference as vi

AID = "44444444-4444-4444-8444-444444444444"
MODEL_DIR: Path = vi.DEFAULT_MODEL_DIR
MODEL_PATH = MODEL_DIR / "crop_leaf_diseases_vit.onnx"

# ------------------------------------------------------------------- helpers
def _settings(url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        vision_inference_url=url,
        vision_inference_token=None,
        agent_timeout_seconds=5,
    )


def _use_shipped_model(monkeypatch) -> None:
    monkeypatch.delenv("VISION_MODEL_DIR", raising=False)
    vi._reset_loader_cache()


def _fresh_session() -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.log_severity_level = 3
    return ort.InferenceSession(str(MODEL_PATH), options, providers=["CPUExecutionProvider"])


def _green_jpeg(size: tuple[int, int] = (640, 640), seed: int = 5) -> bytes:
    rng = np.random.default_rng(seed)
    arr = np.clip(
        np.array([70, 140, 50]) + rng.normal(0, 28, (size[1], size[0], 3)), 0, 255
    ).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _solid_jpeg(rgb: tuple[int, int, int], size: tuple[int, int] = (320, 320)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, rgb).save(buf, "JPEG", quality=95)
    return buf.getvalue()


def _intake() -> dict:
    return {"crop": "wheat", "growth_stage": "tillering", "symptoms": ["yellowing"],
            "symptoms_spreading": "not_sure", "soil_moisture": "not_sure",
            "drainage": "not_sure", "notes": ""}


def _record(raw: bytes, ident: str = "img-1") -> dict:
    return {"id": ident, "read_bytes": lambda: raw}


class _StubSession:
    """Deterministic ONNX output: logits with argmax pinned to one index."""

    def __init__(self, top_index: int, width: int = 13):
        logits = np.zeros((1, width), dtype=np.float32)
        logits[0, top_index] = 5.0
        self._logits = logits

    def get_inputs(self):
        return [SimpleNamespace(name="pixel_values", shape=["batch_size", 3, 224, 224],
                                type="tensor(float)")]

    def get_outputs(self):
        return [SimpleNamespace(name="output", shape=["batch_size", 13], type="tensor(float)")]

    def run(self, _outputs, feeds):
        batch = next(iter(feeds.values()))
        assert batch.dtype == np.float32, "the graph input must be float32"
        return [np.repeat(self._logits, batch.shape[0], axis=0)]


# --------------------------------------------------------------------- tests
def test_onnx_session_metadata_and_io_parsing():
    """1. Session loads; input name/shape/dtype and output name/shape are used."""
    session = _fresh_session()
    inputs, outputs = session.get_inputs(), session.get_outputs()
    assert len(inputs) == 1 and len(outputs) == 1
    assert inputs[0].name == "pixel_values"
    assert list(inputs[0].shape) == ["batch_size", 3, 224, 224]
    assert inputs[0].type == "tensor(float)"
    assert outputs[0].name == "output"
    assert list(outputs[0].shape) == ["batch_size", 13]
    assert outputs[0].type == "tensor(float)"

    bundle, reason = vi._ensure_bundle(MODEL_DIR)
    assert reason is None and bundle is not None
    # The loader derives everything from the graph + shipped config, not guesses.
    assert bundle["input_name"] == inputs[0].name
    assert bundle["layout"] == "NCHW"
    assert bundle["image_size"] == 224
    assert bundle["image_mean"] == [0.5, 0.5, 0.5]
    assert bundle["image_std"] == [0.5, 0.5, 0.5]
    assert bundle["rescale"] == pytest.approx(1 / 255)
    assert bundle["resample"] == 2  # PIL BILINEAR, per preprocessor_config.json
    # Output head width must equal the label map width.
    assert len(bundle["id2label"]) == 13 == outputs[0].shape[1]

    tensor = vi._preprocess(_green_jpeg(), bundle)
    assert tensor is not None
    assert tensor.shape == (3, 224, 224), "NCHW per the graph input"
    assert tensor.dtype == np.float32
    assert -1.0 <= float(tensor.min()) and float(tensor.max()) <= 1.0


def test_preprocess_is_rgb_channel_order_with_config_normalization():
    """RGB (not BGR), rescale 1/255 then (x - 0.5) / 0.5 from config.json."""
    bundle, reason = vi._ensure_bundle(MODEL_DIR)
    assert reason is None and bundle is not None
    tensor = vi._preprocess(_solid_jpeg((255, 0, 0)), bundle)  # pure red
    assert tensor is not None
    # channel 0 must be red -> +1 after normalization, G and B -> -1
    assert float(tensor[0].mean()) > 0.9
    assert float(tensor[1].mean()) < -0.9
    assert float(tensor[2].mean()) < -0.9


def test_output_is_logits_and_softmax_is_applied_once():
    """The graph emits logits (not probabilities); the pipeline normalizes once."""
    session = _fresh_session()
    out = session.run(None, {"pixel_values": np.zeros((1, 3, 224, 224), dtype=np.float32)})[0]
    assert out.shape == (1, 13)
    assert abs(float(out.sum()) - 1.0) > 0.1, "raw output must not already be a distribution"
    assert (out < 0).any(), "raw output must contain negative logits"
    # ...and the diagnostic score is a proper probability in (0, 1].
    diagnostics = vision_adapter._diagnostics("clear", [], raw=_green_jpeg())
    assert diagnostics["model_loaded"] is True
    assert 0.0 < float(diagnostics["raw_top_score"]) <= 1.0
    assert diagnostics["model_input_shape"] == ["batch_size", 3, 224, 224]
    assert diagnostics["model_output_shape"] == ["batch_size", 13]
    assert diagnostics["preprocess_shape"] == [3, 224, 224]
    assert isinstance(diagnostics["raw_top_index"], int)
    assert diagnostics["raw_top_label"]


def test_label_lookup_uses_the_models_actual_id2label_order():
    """2. Index -> label comes from the shipped config.json, in that order."""
    config = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))
    label_map = json.loads((MODEL_DIR / "label_map.json").read_text(encoding="utf-8"))
    expected = {int(k): str(v) for k, v in dict(config["id2label"]).items()}

    bundle, reason = vi._ensure_bundle(MODEL_DIR)
    assert reason is None and bundle is not None
    assert bundle["id2label"] == expected
    for index in range(len(expected)):
        assert bundle["id2label"][index] == config["id2label"][str(index)]
    # The wheat classes sit at the indices the shipped model card records.
    assert expected[10] == "Wheat___Brown_Rust"
    assert expected[11] == "Wheat___Healthy"
    assert expected[12] == "Wheat___Yellow_Rust"
    # label_map.json (model label -> app-safe finding) is used verbatim.
    assert bundle["label_map"] == label_map


@pytest.mark.parametrize(
    "top_index, expected_finding",
    [
        (11, "healthy_looking"),       # Wheat___Healthy
        (10, "rust_like_pustules"),    # Wheat___Brown_Rust
        (12, "rust_like_pustules"),    # Wheat___Yellow_Rust
        (3, "unclear"),                # Invalid (non-wheat)
        (0, "unclear"),                # Corn___Common_Rust (non-wheat)
        (7, "unclear"),                # Rice___Brown_Spot (non-wheat)
    ],
)
def test_mocked_onnx_output_maps_raw_index_to_safe_finding(monkeypatch, top_index, expected_finding):
    """3. Deterministic logits -> raw top-1 -> app-safe visible finding."""
    _use_shipped_model(monkeypatch)
    monkeypatch.setattr(vision_adapter, "get_settings", lambda: _settings(None))
    bundle, reason = vi._ensure_bundle(MODEL_DIR)
    assert reason is None and bundle is not None
    monkeypatch.setitem(bundle, "session", _StubSession(top_index))

    result = asyncio.run(
        vision_adapter.analyze_images(AID, _intake(), [_record(_green_jpeg())])
    )
    diagnostics = result.data["diagnostics"]
    assert diagnostics["model_loaded"] is True
    assert diagnostics["raw_top_index"] == top_index
    assert diagnostics["mapped_visible_finding"] == expected_finding

    if expected_finding == "unclear":
        # Unknown / non-wheat raw label: no wheat finding is asserted, so the
        # wheat-only scope gate abstains - and the mapping still reports unclear.
        assert diagnostics["raw_top_label"] not in bundle["label_map"]
        assert result.status == "unsupported"
        assert result.observations == []
    else:
        assert diagnostics["raw_top_label"] in bundle["label_map"]
        assert bundle["id2label"][diagnostics["raw_top_index"]] in bundle["label_map"]
        assert result.status in {"complete", "partial"}
        assert any(obs.startswith(
            ("No clear visible symptoms", "Rust-like marks visible")
        ) for obs in result.observations)


def test_map_visible_finding_contract():
    """Direct unit check of the documented mapping table."""
    mapping = vision_adapter.WHEAT_VISIBLE_BY_LABEL
    assert vision_adapter.map_visible_finding("Wheat___Healthy", mapping) == "healthy_looking"
    assert vision_adapter.map_visible_finding("Wheat___Brown_Rust", mapping) == "rust_like_pustules"
    assert vision_adapter.map_visible_finding("Wheat___Yellow_Rust", mapping) == "rust_like_pustules"
    for unknown in ("Invalid", "Corn___Healthy", "Rice___Healthy", "Potato___Healthy",
                    "", None, "made_up_label", 7):
        assert vision_adapter.map_visible_finding(unknown, mapping) == "unclear"
    # Without a shipped map the same rules hold from the in-code mirror.
    assert vision_adapter.map_visible_finding("Wheat___Healthy") == "healthy_looking"
    assert vision_adapter.map_visible_finding("Rice___Healthy") == "unclear"


def test_diagnostics_contain_no_bytes_paths_or_secrets():
    """The temporary diagnostics block is safe to expose in result data."""
    diagnostics = vision_adapter._diagnostics("clear", [], raw=_green_jpeg())
    text = json.dumps(diagnostics, default=str)
    assert not any(marker in text for marker in (".jpg", ".png", ".onnx", "C:\\", "/home", "/Users"))
    assert set(diagnostics) == {
        "model_loaded",
        "model_input_shape",
        "model_output_shape",
        "preprocess_shape",
        "raw_top_label",
        "raw_top_index",
        "raw_top_score",
        "quality_state",
        "quality_reasons",
        "mapped_visible_finding",
    }

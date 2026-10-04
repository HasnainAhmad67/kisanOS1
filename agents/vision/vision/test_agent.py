"""Run:  python test_agent.py                       (from this agent folder)
        python -m agents.vision.test_agent           (from the kisanos/ folder)
        pytest agents/vision

The tests build a small STAND-IN ONNX classifier (it picks the class whose prototype colour is closest to the photo's
mean colour). It is a real ONNX graph run by the real onnxruntime and the real agent code, so it proves the
integration works - it says NOTHING about how well any wheat-disease model recognises real diseases.
"""
import contextlib
import io
import json
import os
import re
import shutil
import socket
import tempfile
import uuid
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
from PIL import Image, ImageFilter

try:
    from . import check_model, contract, model as model_mod
    from .agent import analyze_image
    from .contract import REQUIRED_KEYS, validate_contract
    from .quality import check_quality
except ImportError:                     # running directly from the agent folder
    import check_model, contract, model as model_mod
    from agent import analyze_image
    from contract import REQUIRED_KEYS, validate_contract
    from quality import check_quality

HERE = Path(__file__).parent
GREEN, YELLOW, LIGHT, BROWN = (70, 140, 50), (200, 185, 40), (170, 210, 120), (150, 80, 40)
LABELS = ["healthy", "yellow rust", "brown rust", "powdery mildew"]
LABEL_MAP = {"map": {"healthy": "healthy_looking", "yellow rust": "rust_like_pustules", "brown rust": "rust_like_pustules",
                     "powdery mildew": "spots_or_blotches"}, "not_wheat_labels": []}


# ------------------------------------------------------------------------- synthetic photos
def _png(arr) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.clip(arr, 0, 255).astype("uint8")).save(buf, "PNG")
    return buf.getvalue()


def photo(color, w=1000, h=800, seed=1):
    rng = np.random.default_rng(seed)
    return _png(np.array(color, dtype=float) + rng.normal(0, 28, (h, w, 1)))


def mixed_photo(seed=2):                   # left half green leaf, right half brown
    rng = np.random.default_rng(seed)
    a = np.zeros((800, 1000, 3)); a[:, :500], a[:, 500:] = GREEN, BROWN
    return _png(a + rng.normal(0, 28, (800, 1000, 1)))


def mean_colour(*colors):
    return tuple(np.mean(colors, axis=0))


# ------------------------------------------------------------------------- stand-in model
def _norm(c):
    return (np.array(c, dtype=np.float32) / 255 - 0.5) / 0.5


def build_onnx(path, labels, protos, scale=40.0, bias_extra=None, size=32, layout="nchw", dynamic=False,
               fp16=False, softmax=False):
    """logit_k = -scale * ||mean_colour - proto_k||^2   (a linear layer on the spatial mean of the input)."""
    K = len(labels)
    P = np.stack([_norm(p) for p in protos] + [np.zeros(3, np.float32)] * (K - len(protos)))      # K x 3
    W = (2 * scale * P).T.astype(np.float32)                                                      # 3 x K
    b = (-scale * (P ** 2).sum(1)).astype(np.float32)
    if bias_extra is not None:
        b = b + np.array(bias_extra, dtype=np.float32)
    dims = (["N", 3, "h" if dynamic else size, "w" if dynamic else size] if layout == "nchw"
            else ["N", "h" if dynamic else size, "w" if dynamic else size, 3])
    axes = [2, 3] if layout == "nchw" else [1, 2]
    X = helper.make_tensor_value_info("pixel_values", TensorProto.FLOAT16 if fp16 else TensorProto.FLOAT, dims)
    Y = helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["N", K])
    nodes, src = [], "pixel_values"
    if fp16:
        nodes.append(helper.make_node("Cast", ["pixel_values"], ["xf"], to=TensorProto.FLOAT)); src = "xf"
    nodes += [helper.make_node("ReduceMean", [src], ["m"], axes=axes, keepdims=0),
              helper.make_node("MatMul", ["m", "W"], ["z"]),
              helper.make_node("Add", ["z", "b"], ["lg" if softmax else "logits"])]
    if softmax:
        nodes.append(helper.make_node("Softmax", ["lg"], ["logits"], axis=1))
    g = helper.make_graph(nodes, "standin", [X], [Y], [numpy_helper.from_array(W, "W"), numpy_helper.from_array(b, "b")])
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)]); m.ir_version = 8
    onnx.save(m, str(path))


def install(d, labels=LABELS, protos=(GREEN, YELLOW, mean_colour(GREEN, BROWN), LIGHT), label_map=None, card=True,
            pre=None, id2label=True, **kw):
    """Write a complete model folder. protos order = labels order. Defaults: healthy, yellow rust, brown rust, mildew."""
    d = Path(d); d.mkdir(parents=True, exist_ok=True)
    build_onnx(d / "model.onnx", labels, protos, **kw)
    if id2label:
        (d / "config.json").write_text(json.dumps({"id2label": {str(i): l for i, l in enumerate(labels)}}))
    (d / "label_map.json").write_text(json.dumps(label_map if label_map is not None else LABEL_MAP))
    (d / "preprocessor_config.json").write_text(json.dumps(pre if pre is not None else
                                                           {"image_mean": [0.5] * 3, "image_std": [0.5] * 3}))
    if card:
        (d / "model_card.json").write_text(json.dumps({
            "name": "Stand-in colour classifier (tests only)", "url": "https://example.org/standin-model",
            "publisher": "KisanOS test suite", "license": "n/a", "source_status": "unverified"}))
    return d


@contextlib.contextmanager
def using(d):
    old = os.environ.get("VISION_MODEL_DIR")
    os.environ["VISION_MODEL_DIR"] = str(d)
    model_mod.reset_model_cache()
    try:
        yield d
    finally:
        os.environ.pop("VISION_MODEL_DIR", None)
        if old is not None:
            os.environ["VISION_MODEL_DIR"] = old
        model_mod.reset_model_cache()


@contextlib.contextmanager
def model_installed(**kw):
    d = Path(tempfile.mkdtemp())
    try:
        install(d, **kw)
        with using(d):
            yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@contextlib.contextmanager
def no_model():
    d = Path(tempfile.mkdtemp())
    try:
        with using(d):
            yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check(r):
    assert validate_contract(r) == [], validate_contract(r)
    assert tuple(r.keys()) == REQUIRED_KEYS and r["agent_id"] == "vision" and r["provider_or_model"] == "self-hosted"
    assert len(r["sources"]) >= 1                                  # sources are mandatory
    return r


# ================================================================= 1. real model inference =================
def test_healthy_photo_is_classified_by_the_real_onnx_model():
    with model_installed():
        r = check(analyze_image(photo(GREEN)))
    assert r["status"] == "complete" and r["evidence_band"] == "medium"
    assert r["observations"][1].startswith("No visible symptoms: model label 'healthy' (score 1.00)")
    assert "model_score_uncalibrated" in r["safety_flags"] and "expert_referral_recommended" not in r["safety_flags"]
    assert any("not performed by the model" in o for o in r["observations"][:1])           # honest about the crop check
    assert "crop_check_not_performed" in r["safety_flags"]


def test_rust_like_photo_gives_findings_causes_checks_and_expert_referral():
    with model_installed():
        r = check(analyze_image(photo(YELLOW)))
    assert r["status"] == "complete"
    assert r["observations"][1].startswith("Rust-like pustules: model label 'yellow rust'")
    assert any("rust-type" in c.lower() for c in r["possible_causes"])
    assert any("agriculture expert" in c for c in r["checks"]) and any("Rub a leaf" in c for c in r["checks"])
    assert "expert_referral_recommended" in r["safety_flags"] and "Expert review is recommended" in r["summary"]
    assert "diagnos" not in r["summary"].lower().replace("cannot confirm", "")
    for photo_bytes, expected in ((mixed_photo(), "brown rust"), (photo(LIGHT), "powdery mildew")):
        with model_installed():
            assert f"model label '{expected}'" in " ".join(analyze_image(photo_bytes)["observations"])


def test_same_photo_same_answer_and_probabilities_are_real():
    with model_installed():
        a, b = analyze_image(photo(GREEN)), analyze_image(photo(GREEN))
        m, _ = model_mod.get_model()
        preds = m.predict(photo(YELLOW))
    for k in ("status", "summary", "observations", "possible_causes", "checks", "evidence_reason", "safety_flags"):
        assert a[k] == b[k]
    assert a["assessment_id"] != b["assessment_id"]
    assert len(preds) == 4 and abs(sum(p for _, p in preds) - 1) < 1e-5 and preds == sorted(preds, key=lambda t: -t[1])
    assert preds[0][0] == "yellow rust"


def test_evidence_reason_names_the_model_and_its_hash():
    with model_installed() as d:
        r = analyze_image(photo(GREEN))
        sha = model_mod.get_model()[0].sha256
    assert "Stand-in colour classifier" in r["evidence_reason"] and sha[:12] in r["evidence_reason"]
    assert "not been validated on local wheat photos" in r["evidence_reason"] and "uncalibrated" in r["evidence_reason"]


def test_low_score_unmapped_label_and_competing_reading():
    with model_installed(scale=0.2):                               # flat scores -> nothing is sure
        r = check(analyze_image(photo(GREEN)))
    assert r["status"] == "complete" and r["evidence_band"] == "low" and "Unclear" in r["observations"][1]
    assert "low_model_score" in r["safety_flags"] and "expert_referral_recommended" in r["safety_flags"]
    lm = {"map": {"yellow rust": "rust_like_pustules"}}            # the top label 'healthy' is not in the map
    with model_installed(label_map=lm):
        r = check(analyze_image(photo(GREEN)))
    assert "Unclear" in r["observations"][1] and "unrecognised_label_dropped" in r["safety_flags"]
    lm2 = dict(LABEL_MAP, min_probability=0.3)                     # photo exactly between healthy and yellow
    with model_installed(label_map=lm2, scale=8.0):
        r = check(analyze_image(photo(mean_colour(GREEN, YELLOW))))
    obs = " ".join(r["observations"])
    assert "also possible" in obs and r["evidence_band"] == "low"


def test_model_with_an_other_crop_class_rejects_non_wheat():
    labels = LABELS + ["other crop"]
    lm = dict(LABEL_MAP, not_wheat_labels=["Other Crop"])
    with model_installed(labels=labels, label_map=lm, bias_extra=[0, 0, 0, 0, 500]):
        r = check(analyze_image(photo(GREEN)))
    assert r["status"] == "unavailable" and "non_wheat_image" in r["safety_flags"] and r["observations"][0].startswith("Crop detected")
    with model_installed(labels=labels, label_map=lm, bias_extra=[0, 0, 0, 0, -500]):
        r = check(analyze_image(photo(GREEN)))
    assert r["status"] == "complete" and "the model has an 'other crop' class" in r["observations"][0]
    assert "crop_check_not_performed" not in r["safety_flags"]


def test_model_output_that_is_already_probabilities_is_not_softmaxed_twice():
    with model_installed(softmax=True):
        r = check(analyze_image(photo(GREEN)))
        preds = model_mod.get_model()[0].predict(photo(GREEN))
    assert r["status"] == "complete" and abs(sum(p for _, p in preds) - 1) < 1e-5 and preds[0][1] > 0.99


# ================================================================= 2. preprocessing ========================
def test_preprocessing_matches_a_numpy_reference():
    with model_installed(size=32) as d:
        m = model_mod.get_model()[0]
        t = m.preprocess(_png(np.tile(np.array([255, 0, 0], dtype=float), (64, 96, 1))))
    assert t.shape == (1, 3, 32, 32) and t.dtype == np.float32
    assert np.allclose(t[0, 0], 1.0) and np.allclose(t[0, 1], -1.0) and np.allclose(t[0, 2], -1.0)   # (255/255-.5)/.5 etc.
    with model_installed(size=32, layout="nhwc") as d:
        m = model_mod.get_model()[0]
        t = m.preprocess(_png(np.tile(np.array([255, 0, 0], dtype=float), (64, 96, 1))))
        r = check(analyze_image(photo(GREEN)))
    assert t.shape == (1, 32, 32, 3) and np.allclose(t[0, :, :, 0], 1.0) and r["observations"][1].startswith("No visible symptoms")
    with model_installed(size=32, fp16=True):
        m = model_mod.get_model()[0]
        assert m.preprocess(photo(GREEN)).dtype == np.float16
        assert check(analyze_image(photo(GREEN)))["status"] == "complete"


def test_huggingface_style_preprocessor_settings():
    with model_installed(dynamic=True, pre={"size": {"shortest_edge": 40}, "crop_size": {"height": 32, "width": 32},
                                            "image_mean": [0.5] * 3, "image_std": [0.5] * 3}):
        m = model_mod.get_model()[0]
        assert m.preprocess(photo(GREEN, 120, 60)).shape == (1, 3, 32, 32)               # shortest edge 40, centre crop 32
        assert check(analyze_image(photo(YELLOW)))["observations"][1].startswith("Rust-like")
    with model_installed(dynamic=True, pre={"size": {"height": 48, "width": 64}, "image_mean": [0.5] * 3, "image_std": [0.5] * 3}):
        assert model_mod.get_model()[0].preprocess(photo(GREEN)).shape == (1, 3, 48, 64)
    with model_installed(dynamic=True, pre={"size": 24, "image_mean": [0.5] * 3, "image_std": [0.5] * 3}):
        assert model_mod.get_model()[0].preprocess(photo(GREEN)).shape == (1, 3, 24, 24)


# ================================================================= 3. no model = unavailable, never invented ==
def test_without_a_model_the_answer_is_unavailable_not_an_example():
    with no_model():
        r = check(analyze_image(photo(GREEN)))
    assert r["status"] == "unavailable" and r["evidence_band"] == "not_calibrated" and "model_not_available" in r["safety_flags"]
    assert "model.onnx not found" in r["evidence_reason"]
    text = json.dumps(r).lower()
    assert "example" not in text.replace("no example or placeholder", "") and r["possible_causes"] == []
    assert r["observations"] == ["Photo analysis was not performed"]


def test_every_kind_of_broken_install_is_reported_not_hidden():
    cases = {}
    def broken(name, mutate, expect):
        cases[name] = (mutate, expect)
    broken("no label_map", lambda d: (d / "label_map.json").unlink(), "label_map.json not found")
    broken("bad json", lambda d: (d / "label_map.json").write_text("{nope"), "not valid JSON")
    broken("empty map", lambda d: (d / "label_map.json").write_text('{"map": {}}'), "non-empty 'map'")
    broken("unknown class", lambda d: (d / "label_map.json").write_text('{"map": {"healthy": "definitely_not_a_class"}}'), "unknown classes")
    broken("not an onnx file", lambda d: (d / "model.onnx").write_bytes(b"this is not a model"), "could not be loaded")
    broken("label count mismatch", lambda d: (d / "config.json").write_text('{"id2label": {"0": "a", "1": "b"}}'), "do not match the 2 labels")
    broken("bad id2label", lambda d: (d / "config.json").write_text('{"id2label": {"x": "a"}}'), "keys must be integers")
    broken("no labels at all", lambda d: (d / "config.json").unlink(), "no class labels")
    broken("bad probabilities", lambda d: (d / "label_map.json").write_text('{"map": {"healthy": "healthy_looking"}, "min_probability": "x"}'), "must be numbers")
    for name, (mutate, expect) in cases.items():
        with model_installed() as d:
            mutate(d); model_mod.reset_model_cache()
            r = check(analyze_image(photo(GREEN)))
        assert r["status"] == "unavailable" and "model_not_available" in r["safety_flags"], name
        assert expect in r["evidence_reason"], (name, r["evidence_reason"])


def test_labels_txt_and_label_map_labels_are_accepted_and_env_dir_override_reloads():
    with model_installed(id2label=False) as d:
        (d / "labels.txt").write_text("\n".join(LABELS))
        model_mod.reset_model_cache()
        assert check(analyze_image(photo(GREEN)))["status"] == "complete"
    with model_installed(id2label=False, label_map=dict(LABEL_MAP, labels=LABELS)):
        assert check(analyze_image(photo(GREEN)))["status"] == "complete"
    with model_installed() as d:                                    # replacing model.onnx is picked up without restart
        assert "model label 'healthy'" in analyze_image(photo(GREEN))["observations"][1]
        build_onnx(d / "model.onnx", LABELS, (YELLOW, GREEN, BROWN, LIGHT))      # now 'healthy' is the yellow prototype
        os.utime(d / "model.onnx", None)
        assert "model label 'yellow rust'" in analyze_image(photo(GREEN))["observations"][1]


def test_inference_failure_returns_unavailable():
    with model_installed():
        m = model_mod.get_model()[0]
        old = m.predict
        m.predict = lambda b: 1 / 0
        try:
            r = check(analyze_image(photo(GREEN)))
        finally:
            m.predict = old
    assert r["status"] == "unavailable" and "model_inference_failed" in r["safety_flags"]


# ================================================================= 4. quality gate =========================
def test_quality_gate_rejects_bad_photos_and_still_returns_a_source():
    blur = io.BytesIO()
    Image.open(io.BytesIO(photo(GREEN))).filter(ImageFilter.GaussianBlur(12)).save(blur, "PNG")
    rng = np.random.default_rng(3)
    grey = np.clip(rng.normal(128, 40, (800, 1000, 1)).repeat(3, axis=2), 0, 255)
    cases = {"blurry": blur.getvalue(), "too_dark": _png(np.array(Image.open(io.BytesIO(photo(GREEN)))) * 0.1),
             "no_plant": _png(grey), "low_resolution": photo(GREEN, 200, 150), "bad_file": b"not an image"}
    with model_installed():
        for issue, data in cases.items():
            r = check(analyze_image(data))
            assert r["status"] == "unavailable" and "photo_quality_failed" in r["safety_flags"], issue
            assert any(issue.replace("_", " ") in o for o in r["observations"]), (issue, r["observations"])
            assert r["evidence_band"] == "not_calibrated"
        huge = io.BytesIO(); Image.new("L", (7000, 7000)).save(huge, "PNG")
        assert "too_many_pixels" in check_quality(huge.getvalue())["issues"]
        assert check(analyze_image(huge.getvalue()))["status"] == "unavailable"


# ================================================================= 5. safety ===============================
def test_banned_words_from_model_labels_or_farmer_text_never_reach_the_output():
    labels = ["healthy", "spray damage", "brown rust", "powdery mildew"]
    lm = {"map": {"healthy": "healthy_looking", "spray damage": "drying", "brown rust": "rust_like_pustules",
                  "powdery mildew": "spots_or_blotches"}}
    with model_installed(labels=labels, label_map=lm):
        r = check(analyze_image(photo(YELLOW), growth_stage="tillering; spray urea 50 kg"))
    assert "spray" not in json.dumps(r).lower() and "urea" not in json.dumps(r).lower()
    assert "unsafe_advice_removed" in r["safety_flags"]
    with model_installed():
        r = check(analyze_image(photo(GREEN), growth_stage="Tillering"))
    assert "Farmer-reported growth stage: Tillering." in r["summary"]


def test_confidence_is_never_high_and_never_a_diagnosis():
    with model_installed():
        for data in (photo(GREEN), photo(YELLOW), mixed_photo(), photo(LIGHT)):
            r = check(analyze_image(data))
            assert r["evidence_band"] in ("low", "medium")
            assert "cannot confirm cause" in r["summary"]


def test_never_raises_on_junk_input():
    with model_installed():
        for junk in (None, "text", 5, b"", b"\x00" * 1000, [1, 2], {"a": 1}, bytearray(b"abc")):
            check(analyze_image(junk))
    with no_model():
        check(analyze_image(None))
    r = check(analyze_image(photo(GREEN), assessment_id="not-a-uuid"))
    mine = str(uuid.uuid4())
    assert uuid.UUID(r["assessment_id"]) and check(analyze_image(photo(GREEN), assessment_id=mine))["assessment_id"] == mine


# ================================================================= 6. contract =============================
def test_all_outputs_have_the_14_fields_pass_both_validators_and_have_sources():
    scenarios = []
    with model_installed():
        scenarios += [analyze_image(photo(c)) for c in (GREEN, YELLOW, LIGHT)] + [analyze_image(b"junk")]
    with model_installed(card=False):
        scenarios.append(analyze_image(photo(GREEN)))
    with no_model():
        scenarios.append(analyze_image(photo(GREEN)))
    scenarios.append(contract.error_contract(None, RuntimeError("x")))
    schema = json.loads((HERE / "schema.json").read_text())
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    try:
        from pydantic import ValidationError
        from .schema import VisionOutput
    except ImportError:
        try:
            from schema import VisionOutput
        except ImportError:
            VisionOutput = None
    for r in scenarios:
        check(r)
        assert set(s["source_status"] for s in r["sources"]) <= {"official", "supporting", "secondary", "unverified"}
        assert all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", s["retrieved_at"]) for s in r["sources"])
        if jsonschema:
            jsonschema.validate(r, schema)
        if VisionOutput:
            VisionOutput(**r)
    assert {r["status"] for r in scenarios} == {"complete", "unavailable", "error"}


def test_sources_include_the_model_when_its_card_exists_and_always_the_symptom_reference():
    with model_installed():
        r = analyze_image(photo(YELLOW))
    urls = [s["url"] for s in r["sources"]]
    assert urls[0] == "https://example.org/standin-model" and "https://pmc.ncbi.nlm.nih.gov/articles/PMC10953319" in urls
    assert "self-hosted open-source vision model" in r["sources"][0]["title"]
    with model_installed(card=False):
        r = analyze_image(photo(YELLOW))
    assert [s["url"] for s in r["sources"]] == ["https://pmc.ncbi.nlm.nih.gov/articles/PMC10953319"]
    bad = dict(check(analyze_image(photo(GREEN))))
    bad["sources"] = []
    assert validate_contract(bad) and any("mandatory" in p for p in validate_contract(bad))


def test_validator_catches_contract_violations():
    with model_installed():
        good = check(analyze_image(photo(GREEN)))
    def broke(**ch): return validate_contract({**good, **ch})
    assert broke(status="ok") and broke(evidence_band="great") and broke(created_at="2026-10-04") and broke(assessment_id="1")
    assert broke(provider_or_model="somewhere") and broke(observations="x") and broke(summary="Spray the crop")
    assert broke(sources=[{"title": "t"}]) and broke(checks=["use 5 kg per acre"])
    reordered = {k: good[k] for k in reversed(list(good))}
    assert validate_contract(reordered)


# ================================================================= 7. really self-hosted: no dummy, no cloud ==
def test_no_dummy_no_cloud_api_no_network_code_in_the_package():
    assert not (HERE / "dummy.py").exists() and not (HERE / "llm.py").exists()
    banned = [r"import\s+urllib", r"from\s+urllib", r"import\s+requests", r"import\s+socket", r"http\.client",
              r"API_KEY", r"generativelanguage", r"api\.groq", r"force_dummy", r"dummy_result", r"google\.generativeai", r"import\s+groq"]
    for p in HERE.glob("*.py"):
        if p.name == "test_agent.py":
            continue
        text = p.read_text(encoding="utf-8")
        for pat in banned:
            assert not re.search(pat, text, re.I), (p.name, pat)
    import inspect
    assert "force_dummy" not in inspect.signature(analyze_image).parameters


def test_works_with_the_network_switched_off():
    real = socket.socket
    def blocked(*a, **k): raise OSError("network disabled for this test")
    socket.socket = blocked
    try:
        with model_installed():
            r = check(analyze_image(photo(YELLOW)))
    finally:
        socket.socket = real
    assert r["status"] == "complete" and r["observations"][1].startswith("Rust-like")


# ================================================================= 8. self-check tool =======================
def test_check_model_tool():
    buf = io.StringIO()
    with model_installed():
        with contextlib.redirect_stdout(buf):
            assert check_model.main([]) == 0
    out = buf.getvalue()
    assert "Stand-in colour classifier" in out and "status=complete" in out
    buf = io.StringIO()
    with no_model():
        with contextlib.redirect_stdout(buf):
            assert check_model.main([]) == 1
    assert "MODEL NOT AVAILABLE" in buf.getvalue()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")

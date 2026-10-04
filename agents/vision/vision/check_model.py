"""Check that the self-hosted vision model is installed and really runs, and try it on your own photos.

    python -m agents.vision.check_model                    (from the kisanos/ folder; no photo = synthetic image)
    python -m agents.vision.check_model leaf1.jpg leaf2.jpg

It prints the model files it found, the model's top-5 labels for each photo and the final 14-field JSON status.
With no photo it only proves the model LOADS and RUNS - it says nothing about accuracy. Judge accuracy by
running 20-30 real wheat photos (healthy and diseased) and comparing with an expert.
Exit code 0 = model works, 1 = model not available.
"""
import io
import json
import sys

import numpy as np
from PIL import Image

try:
    from . import model as model_mod
    from .agent import analyze_image
except ImportError:                     # running directly from the agent folder
    import model as model_mod
    from agent import analyze_image


def _synthetic() -> bytes:
    rng = np.random.default_rng(1)
    arr = np.clip(np.array([70, 140, 50]) + rng.normal(0, 28, (800, 1000, 1)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def main(argv) -> int:
    m, err = model_mod.get_model()
    print("model folder :", model_mod.model_dir())
    if m is None:
        print("MODEL NOT AVAILABLE:", err)
        print("See models/README.md for how to install a model.")
        return 1
    d = m.describe()
    print(f"model        : {d['name']}  (sha256 {m.sha256[:16]}...)  license: {d['license']}")
    print(f"labels ({d['labels']})  : {', '.join(m.labels)}")
    print(f"input        : {m.input_name}, {'NHWC' if m.nhwc else 'NCHW'}, fixed size {m.static_hw}")
    photos = [(p, open(p, "rb").read()) for p in argv] or [("(synthetic green image - proves the model runs only)", _synthetic())]
    for name, data in photos:
        print("\n== photo:", name)
        try:
            for label, p in m.predict(data):
                print(f"   {p:6.3f}  {label}")
        except Exception as e:
            print("   prediction failed:", type(e).__name__, e)
        r = analyze_image(data)
        print(f"   contract: status={r['status']} band={r['evidence_band']} provider={r['provider_or_model']} flags={r['safety_flags']}")
        print("   observations:", *r["observations"], sep="\n     - ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

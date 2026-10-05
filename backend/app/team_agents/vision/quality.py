"""Image-quality gate for the KisanOS Vision Agent.

Runs BEFORE any analysis. Uses only Pillow + numpy (no OpenCV needed).

Every photo is sorted into exactly one of three states, and each state is
decided only by evidence measured on the photo itself:

    blocked      corrupt / unreadable, <96 px, near-black or near-white
                 (plus the file-size upload envelope) -> the model is NOT run.
    soft_warning proven blur, or a decodable photo whose short side is
                 below 512 px -> the model IS run, flagged low-quality.
    clear        everything else (>=512 px short side with usable exposure)
                 -> the model is run with no quality flag at all.

Notes on the thresholds (measured on the shipped fixtures and on blur/resize
ladders - see tests/test_vision_quality_state.py):

* BLUR_MIN = 25: the Laplacian variance of *sharp* photos measured 41-15471
  while genuinely blurred photos measured 0.2-14, so 25 only fires on proven
  blur. The old threshold of 100 flagged sharp close-ups (41-97) and pushed
  them into the low-quality banner.
* MIN_SHORT_SIDE = 512: a clear, sharp >=512 px photo must read as `clear`.
* `plant_fraction` / `no_plant` is reported as an observation only. "No crop
  visible" is a content hint - not evidence about blur, exposure or detail -
  so it never gates inference. Hard blocks stay limited to corrupt /
  unreadable / <96 px / near-black / near-white.
"""
import io
import numpy as np
from PIL import Image

MAX_BYTES = 10 * 1024 * 1024
# >= MIN_SHORT_SIDE on the short side is "clear" by default.
MIN_SHORT_SIDE = 512
# Hard-block floor: below this no visible-sign screening can run at all.
MIN_ACCEPT_SIDE = 96
# Proven blur only (see module docstring); any blur below this is SOFT.
BLUR_MIN = 25.0
BRIGHT_MIN = 40.0
BRIGHT_MAX = 220.0
PLANT_MIN_FRACTION = 0.10

CLEAR = "clear"
SOFT_WARNING = "soft_warning"
BLOCKED = "blocked"

TIPS = {
    "too_large": "The photo file is too big. Please send a photo under 10 MB.",
    "bad_file": "This file could not be opened as a photo. Please send a JPG or PNG.",
    "low_resolution": "The photo is too small. Please take it with the normal camera at full quality.",
    "blurry": "The photo is blurry. Hold the phone steady and tap the leaf to focus.",
    "too_dark": "The photo is too dark. Please take it in daylight.",
    "too_bright": "The photo is too bright or has glare. Please avoid direct sun on the camera.",
    "no_plant": "No crop is visible. Please move closer so the leaves fill most of the photo.",
}


def _laplacian_variance(gray: np.ndarray) -> float:
    g = gray.astype(np.float64)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def _plant_fraction(img: Image.Image) -> float:
    hsv = np.asarray(img.convert("HSV")).astype(np.int32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    # PIL hue is 0-255. Roughly 40-150 degrees (yellow-green to green) -> 28-106
    mask = (h >= 28) & (h <= 106) & (s >= 40) & (v >= 40)
    return float(mask.mean())


def _finalise(result: dict) -> dict:
    """Derive quality_state / quality_reasons / passed from the measured issues."""
    if result["hard_issues"]:
        state = BLOCKED
    elif result["soft_issues"]:
        state = SOFT_WARNING
    else:
        state = CLEAR
    result["quality_state"] = state
    # Reasons that determined the state only; informational notes stay in
    # `issues` (and `tips`) but never change the state.
    result["quality_reasons"] = sorted(set(result["hard_issues"] + result["soft_issues"]))
    result["passed"] = state == CLEAR
    return result


def check_quality(image_bytes: bytes) -> dict:
    """Grade one photo: `quality_state` is `clear` | `soft_warning` | `blocked`.

    Tiering:
      * hard_issues  -> quality_state="blocked"; the Vision Agent must NOT run
        the model (corrupt, unreadable, <96 px, near-black, near-white, or an
        oversized upload envelope);
      * soft_issues  -> quality_state="soft_warning"; the model runs and the
        result is flagged low-quality / low-confidence;
      * informational notes (e.g. no_plant) are reported in `issues`/`tips`
        but do not gate inference;
      * `passed` / `issues` keep their original strict meaning of "usable
        without any warning" (`passed` == quality_state == "clear").
    """
    result = {"passed": False, "quality_state": BLOCKED, "quality_reasons": [],
              "blur_score": None, "brightness": None,
              "plant_fraction": None, "width": None, "height": None,
              "issues": [], "tips": [], "hard_issues": [], "soft_issues": []}

    def fail(code, tier="hard"):
        result["issues"].append(code)
        result["tips"].append(TIPS[code])
        if tier == "hard":
            result["hard_issues"].append(code)
        elif tier == "soft":
            result["soft_issues"].append(code)

    if len(image_bytes) > MAX_BYTES:
        fail("too_large")
        return _finalise(result)
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        img = img.convert("RGB")
    except Exception:
        fail("bad_file")
        return _finalise(result)

    result["width"], result["height"] = img.size
    if min(img.size) < MIN_ACCEPT_SIDE:
        # <96 px: hard block. 96-511 px: soft warning (inference still runs).
        fail("low_resolution")
    elif min(img.size) < MIN_SHORT_SIDE:
        fail("low_resolution", tier="soft")

    # Work on a downscaled copy so scores do not depend on phone megapixels
    work = img.copy()
    work.thumbnail((1280, 1280))
    gray = np.asarray(work.convert("L"))
    result["blur_score"] = round(_laplacian_variance(gray), 1)
    result["brightness"] = round(float(gray.mean()), 1)
    result["plant_fraction"] = round(_plant_fraction(work), 3)

    if result["blur_score"] < BLUR_MIN:
        # Proven blur only, and always SOFT: a decodable photo still runs the
        # model with a low-confidence warning instead of being discarded.
        fail("blurry", tier="soft")
    if result["brightness"] < BRIGHT_MIN:
        fail("too_dark")
    elif result["brightness"] > BRIGHT_MAX:
        fail("too_bright")
    if result["plant_fraction"] < PLANT_MIN_FRACTION:
        # Observation only - never a gate (see module docstring).
        fail("no_plant", tier="note")

    return _finalise(result)

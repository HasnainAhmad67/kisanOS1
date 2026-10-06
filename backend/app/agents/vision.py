from __future__ import annotations

import asyncio
import io
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import numpy as np
from PIL import Image, ImageOps

from app.core.config import get_settings
from app.schemas import AgentResult, Source
from app.services import vision_inference as vi
from app.services.vision_inference import predict_locally
from app.team_agents.vision.quality import (
    BLOCKED,
    CLEAR,
    MIN_ACCEPT_SIDE,
    SOFT_WARNING,
    TIPS,
    check_quality,
)

VERSION = "vision-gateway-1.0.0"
ALLOWED_CLASSES = {
    "healthy_looking",
    "yellowing",
    "rust_like_pustules",
    "spots_or_blotches",
    "visible_insects",
    "drying",
    "unclear",
}
LABELS = {
    "healthy_looking": "No clear visible symptoms",
    "yellowing": "Visible yellowing",
    "rust_like_pustules": "Rust-like marks visible; cause not confirmed",
    "spots_or_blotches": "Visible spots or blotches",
    "visible_insects": "Visible insects",
    "drying": "Visible drying",
    "unclear": "Image details unclear",
}
UNSAFE_MODEL_TEXT = re.compile(
    r"\b(diagnos\w*|confirm\w*|definit\w*|pesticid\w*|fungicid\w*|insecticid\w*|herbicid\w*|chemical\w*|spray\w*|dose\w*|urea|dap|treat\w*|infection\w*|pathogen\w*|irrigat\w*|yield\w*|guarantee\w*|cure\w*|recommend\w*)\b",
    re.IGNORECASE,
)
# Soft-warning (low-quality) photos may only surface this safe vocabulary.
LOW_QUALITY_CLASSES = {"healthy_looking", "rust_like_pustules"}

# Raw model label -> app-safe visible finding. This is the in-code mirror of
# models/wheat_vision/label_map.json; when the shipped bundle is available the
# mapping is read from that file instead (see map_visible_finding).
WHEAT_VISIBLE_BY_LABEL = {
    "Wheat___Healthy": "healthy_looking",
    "Wheat___Brown_Rust": "rust_like_pustules",
    "Wheat___Yellow_Rust": "rust_like_pustules",
}


def map_visible_finding(raw_label: str | None, label_map: dict[str, str] | None = None) -> str:
    """Map a raw ONNX top-1 label to the app-safe visible finding.

    * Wheat Healthy          -> ``healthy_looking``
    * Wheat Brown Rust / Yellow Rust -> ``rust_like_pustules``
    * any other, non-wheat, ``Invalid`` or unknown label -> ``unclear``

    ``label_map`` is the shipped ``label_map.json`` as loaded from the model
    directory (so the model's own labels are authoritative); the module
    constant is the fallback mirror of that file.
    """
    mapping = WHEAT_VISIBLE_BY_LABEL if label_map is None else label_map
    visible = mapping.get(raw_label) if isinstance(raw_label, str) else None
    return visible if visible in ALLOWED_CLASSES else "unclear"


# --------------------------------------------------------------------------
# Structured photo screening report (`data.photo_report`).
#
# Every sentence here is fixed, farmer-facing visible-sign wording: it never
# names a disease, never states a cause, and never recommends a product,
# dose, treatment, irrigation or money. The enums are closed so the UI can
# localize the status/category from codes instead of reading English prose.
# --------------------------------------------------------------------------

# Photo retake instruction, used by the limited and the blocked report.
_REPORT_RETAKE = (
    "Take a clear close-up photo of one affected leaf in daylight, with the "
    "leaf filling most of the frame."
)

# --- clear photo + healthy-looking mapping
_HEALTHY_VISIBLE = ["Leaf surface appears generally even in colour."]
_HEALTHY_NOT_VISIBLE = [
    "No clear rust-like raised marks are visible in this photo.",
    "No large distinct spots are clearly visible in this photo.",
]
_HEALTHY_INTERPRETATION = (
    "This photo does not show clear visible warning signs. A single photo "
    "cannot rule out problems elsewhere in the field."
)
_HEALTHY_CHECKS = [
    "Inspect both sides of several leaves in this area for any marks or spots.",
    "Compare this plant with a few nearby plants in the same field.",
]

# --- clear photo + rust-like mapping (only ever "may be present")
_RUST_VISIBLE = ["Scattered orange-brown round marks are visible on the leaf surface."]
_RUST_NOT_VISIBLE = ["The cause of these marks cannot be seen in a photo."]
_RUST_INTERPRETATION = (
    "Rust-like visible signs may be present. The cause is not confirmed from "
    "a photo alone."
)
_RUST_CHECKS = [
    "Inspect both sides of 5–10 affected leaves for raised orange, yellow, or brown marks.",
    "Compare affected plants with nearby healthy-looking plants.",
    "Check whether newer leaves are becoming affected.",
]
_RUST_EXPERT_SIGNS = [
    "Marks spread quickly",
    "New leaves become affected",
    "A larger part of the field is affected",
]

# --- clear photo, sign not classifiable by this screening
_UNCLEAR_INTERPRETATION = (
    "Photo quality was adequate, but the visible sign could not be "
    "classified by this screening model."
)
_UNCLASSIFIED_INTERPRETATION = (
    "Photo quality was adequate, but the visible sign reported on the photo "
    "is not one of the healthy-looking or rust-like signs this screening "
    "reports."
)
_NOT_VISIBLE_ANY = ["A plant leaf is visible in the photo."]
_NOT_CLASSIFIED = ["This screening could not say which visible sign is present."]

# --- soft warning (limited) photo
_LIMITED_INTERPRETATION = (
    "A preliminary visible-sign screening was still performed on this photo. "
    "Because the photo quality is limited, this photo cannot rule out visible "
    "signs."
)
_LIMITED_NOT_VISIBLE = [
    "A single photo cannot show conditions elsewhere in the field.",
]

# --- hard-blocked photo: nothing was screened
_BLOCKED_INTERPRETATION = (
    "No uploaded photo passed the photo-quality checks, so no visible-sign "
    "screening was performed."
)
_BLOCKED_NOT_VISIBLE = ["No photo could be reviewed, so nothing was checked."]

# --- photo outside leaf-screening scope (ear/head, field, other plant part,
# --- unclear subject): the sign stays "unclear" and the scope is explained.
_SCOPE_NOT_VISIBLE = ["Leaf symptoms cannot be assessed from this photo."]
_SCOPE_CHECK = [
    "Inspect the leaves on this plant and a few nearby plants for any marks or spots."
]
_SCOPE_RETAKE = (
    "Take a clear daylight close-up of one affected leaf, with the leaf "
    "filling most of the frame."
)
_EAR_VISIBLE = ["A mature wheat ear/head is visible in this photo."]
# The ONE plain-language scope explanation for a clear ear/head photo. It is
# what the farmer reads; the algorithmic classification reason stays in the
# collapsed Technical details of the card.
_EAR_INTERPRETATION = (
    "This is a clear photo of a mature wheat ear/head, not a leaf."
)
# Said only once the subject was identified as an ear/head, so the frame is
# known not to be a leaf close-up (never claimed for an unidentified subject).
_EAR_NOT_VISIBLE = [
    "Leaf symptoms cannot be assessed because this image does not show a "
    "close-up leaf."
]
_FIELD_VISIBLE = ["Crop context is visible across the field in this photo."]
_FIELD_INTERPRETATION = (
    "This image is clear, but it shows the crop from a distance. Leaf-level "
    "symptoms cannot be assessed from a whole-field or distant photo."
)
_OTHER_VISIBLE = ["Plant material is visible, but it is not a close-up wheat leaf."]
_OTHER_INTERPRETATION = (
    "This photo does not show a close-up wheat leaf, so leaf-sign screening "
    "was not applied."
)
_SUBJECT_UNCLEAR_VISIBLE = ["The subject of this photo could not be identified clearly."]
_SUBJECT_UNCLEAR_INTERPRETATION = (
    "The photo subject could not be identified, so leaf-sign screening was "
    "not applied."
)
# A soft-warning photo cannot claim that the image itself is clear.
_SCOPE_LIMITED_INTERPRETATION = (
    "The photo quality is limited, and this screening is designed for "
    "close-up leaf signs, so leaf symptoms were not assessed from this photo."
)

_SUBJECT_VISIBLE: dict[str, list[str]] = {
    "wheat_ear_or_head": _EAR_VISIBLE,
    "whole_field_or_distant_crop": _FIELD_VISIBLE,
    "other_plant_part": _OTHER_VISIBLE,
    "unclear": _SUBJECT_UNCLEAR_VISIBLE,
}
_SUBJECT_INTERPRETATION: dict[str, str] = {
    "wheat_ear_or_head": _EAR_INTERPRETATION,
    "whole_field_or_distant_crop": _FIELD_INTERPRETATION,
    "other_plant_part": _OTHER_INTERPRETATION,
    "unclear": _SUBJECT_UNCLEAR_INTERPRETATION,
}
# One observation per out-of-scope subject: no leaf-sign wording can travel.
_SUBJECT_OBSERVATION: dict[str, str] = {
    "wheat_ear_or_head": "Wheat ear/head visible in the photo; leaf-sign screening was not applied.",
    "whole_field_or_distant_crop": (
        "Crop visible from a distance in the photo; a close-up of one "
        "affected leaf is needed."
    ),
    "other_plant_part": "Plant material visible in the photo, but it is not a close-up wheat leaf.",
    "unclear": "The photo subject could not be identified, so leaf-sign screening was not applied.",
}

# Reasons the gateway can raise that the quality gate's TIPS table has no
# entry for; they still need a farmer-safe explanation in the report.
_EXTRA_QUALITY_TIPS = {
    "image_unreadable": "This photo could not be read. Please send a JPG or PNG photo.",
    "no_image_supplied": "No photo was supplied, so nothing could be checked.",
}
_ALL_QUALITY_TIPS = {**_EXTRA_QUALITY_TIPS, **TIPS}


def _farmer_quality_reasons(reasons: list[str], limit: int = 3) -> list[str]:
    """The gate's own reasons, in farmer-safe wording (gate tips first)."""
    seen: list[str] = []
    for reason in reasons:
        tip = _ALL_QUALITY_TIPS.get(str(reason))
        if tip and tip not in seen:
            seen.append(tip)
    return seen[:limit]


# ---------------------------------------------------- screening scope
# Plant-part / screening-scope result (`photo_subject`, `screening_scope`,
# `scope_reasons`). Deterministic and conservative: only PIL + numpy signals
# this repo already has (colour bands, frame coverage, plant-mask shape, one
# connected-component ratio and a local-detail/defocus share). It is NOT a
# botanical classifier and does not claim to be one - when the plant part
# cannot be identified with defensible evidence the answer is `unclear` /
# `subject_unclear`. A ripe golden ear close-up carries no green leaf band and
# no bright straw band, so it is identified by ripe head colour only when the
# model established wheat AND every ear indicator holds at once.
#
# Critical rule: a leaf finding is only ever reported when the frame is a
# leaf close-up (`leaf_screening_applicable`). A wheat ear/head, a whole-field
# shot, another plant part and an unclear subject all stay `unclear`, so a
# natural golden/brown ear or field texture can never reach a farmer as
# "rust-like marks visible on the leaf surface".
PHOTO_SUBJECTS = (
    "wheat_leaf",
    "wheat_ear_or_head",
    "whole_field_or_distant_crop",
    "other_plant_part",
    "unclear",
)
SCREENING_SCOPES = (
    "leaf_screening_applicable",
    "leaf_screening_not_applicable",
    "subject_unclear",
)

# Frame-coverage thresholds as fractions of a <=512 px thumbnail.
_LEAF_FILL_MIN = 0.35  # a leaf close-up fills the frame with plant material
_LEAF_GREEN_MIN = 0.25  # leaf green must dominate a leaf close-up
_STRAW_MIN = 0.30  # golden straw-coloured head texture dominates the frame
_SKY_MIN = 0.15  # horizon / open sky across the top third => wider view
_COHERENCE_MIN = 0.45  # one coherent plant region vs many small patches
_HEAD_TOP_MIN = 2.0  # upright plant: top at least twice as wide as the base
_PLANT_MIN = 0.10  # any plant material at all before naming a plant part

# Mature (ripe) head colour. A clear close-up of a ripe golden ear sits at
# PIL hue ~14-28 with only moderate saturation, i.e. it misses BOTH the green
# leaf band (hue >= 40) and the bright straw band (hue >= 26, sat >= 70) - the
# frame then measures as "no plant at all" and used to fall through to
# `unclear`. Measured on the shipped wheat close-up: ripe 0.75, defocus 0.31.
_RIPE_HUE_MIN = 15  # ~21 deg: warm tan / ripe golden wheat, below the straw band
_RIPE_HUE_MAX = 41  # ~58 deg: top of the existing straw band
_RIPE_SAT = 45
_RIPE_VAL = 80
_RIPE_MIN = 0.30  # substantial mature head-colour coverage
_DEFOCUS_MIN = 0.20  # near-field close-up: one large smooth (defocused) region
_DEFOCUS_WINDOW = 7  # px window of the local-detail check (<=512 px thumbnail)
_DEFOCUS_LIMIT = 4.0  # grey spread below this reads as a smooth region

# Farmer-safe scope reasons (they are shown in the photo screening report).
_REASON_LEAF_FILL = (
    "The photo is a close-up that fills the frame with leaf material, so "
    "leaf-sign screening applies."
)
_REASON_EAR_STRAW = (
    "Golden straw-coloured head texture fills the frame, so this photo shows "
    "a wheat ear/head rather than a leaf."
)
_REASON_EAR_SHAPE = (
    "The photo shows an upright wheat plant against a background instead of a "
    "leaf close-up, so it shows an ear/head rather than a leaf."
)
_REASON_EAR_COLOUR = (
    "The photo is a clear close-up filled with mature golden wheat head "
    "colour rather than leaf material, so it shows an ear/head rather than "
    "a leaf."
)
_REASON_FIELD_SKY = (
    "A horizon and open sky are visible, so this is a wider field view rather "
    "than a leaf close-up."
)
_REASON_FIELD_PATCHES = (
    "The crop appears as many small separate patches rather than one "
    "close-up, so this is a wider field view."
)
_REASON_NOT_A_LEAF_CLOSEUP = (
    "The frame does not fill with leaf material, so leaf-sign screening was "
    "not applied."
)
_REASON_OTHER_PLANT = (
    "Plant material is visible, but this photo does not show a close-up "
    "wheat leaf."
)
_REASON_NO_WHEAT = (
    "Wheat was not established from this photo, so wheat leaf screening was "
    "not applied."
)
_REASON_SUBJECT_UNCLEAR = (
    "The photo does not show enough detail to identify the plant part."
)
_REASON_SUBJECTS_MIXED = (
    "The photos do not all show the same subject; one clear close-up of a "
    "single affected leaf is needed."
)
_REASON_QUALITY_FAILED = (
    "No photo passed the quality checks, so the photo subject could not be "
    "identified."
)
_REASON_NO_PHOTO = (
    "No photo was supplied, so the photo subject could not be identified."
)

# A hard-blocked photo identifies no subject: nothing was screened at all.
BLOCKED_SCOPE: dict[str, Any] = {
    "photo_subject": "unclear",
    "screening_scope": "subject_unclear",
    "scope_reasons": [_REASON_QUALITY_FAILED],
}


def _largest_component_ratio(mask: np.ndarray) -> float:
    """Share of masked pixels inside the largest blob (128 px grid).

    A close-up is one coherent region; a distant field breaks into many small
    patches. Cheap union-by-visit, no new dependency.
    """
    grid = np.asarray(
        Image.fromarray((mask * 255).astype("uint8")).resize((128, 128), Image.BOX)
    )
    blob = grid >= 110
    total = int(blob.sum())
    if not total:
        return 0.0
    seen = np.zeros_like(blob, dtype=bool)
    largest = 0
    for start_y, start_x in zip(*np.nonzero(blob)):
        if seen[start_y, start_x]:
            continue
        stack = [(int(start_y), int(start_x))]
        seen[start_y, start_x] = True
        size = 0
        while stack:
            cy, cx = stack.pop()
            size += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < 128 and 0 <= nx < 128 and blob[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        largest = max(largest, size)
    return largest / total


def _smooth_share(
    gray: np.ndarray, window: int = _DEFOCUS_WINDOW, limit: float = _DEFOCUS_LIMIT
) -> float:
    """Share of pixels sitting inside a locally flat (smooth) region.

    A near-field close-up separates its subject from a smooth, defocused
    background, while a dense whole-field view carries fine texture across
    every part of the frame - that is what keeps a ripe field from reading as
    an ear. Integral-image box filter over the <=512 px thumbnail, numpy only.
    """
    pad = window // 2
    height, width = gray.shape

    def window_sum(values: np.ndarray) -> np.ndarray:
        # Edge-padded so every output pixel has a full window centred on it.
        padded = np.pad(values.astype(np.float64), pad, mode="edge")
        integral = np.pad(
            np.cumsum(np.cumsum(padded, axis=0), axis=1), ((1, 0), (1, 0))
        )
        return (
            integral[window : window + height, window : window + width]
            - integral[:height, window : window + width]
            - integral[window : window + height, :width]
            + integral[:height, :width]
        )

    mean = window_sum(gray) / (window * window)
    mean_sq = window_sum(gray.astype(np.float64) ** 2) / (window * window)
    variance = np.clip(mean_sq - mean * mean, 0.0, None)
    return float((np.sqrt(variance) < limit).mean())


def _subject_signals(raw: bytes) -> dict[str, float] | None:
    """Colour / coverage / shape signals of one photo, or None if unreadable."""
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except Exception:  # noqa: BLE001 - unreadable bytes simply mean "unknown".
        return None
    image = image.copy()
    image.thumbnail((512, 512))
    hsv = np.asarray(image.convert("HSV")).astype(np.int32)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    # PIL hue runs 0-255 for 0-360 degrees.
    leaf_green = (hue >= 40) & (hue <= 122) & (sat >= 40) & (val >= 40)
    straw = (hue >= 26) & (hue <= 41) & (sat >= 70) & (val >= 110)
    sky = ((hue >= 134) & (hue <= 178) & (sat < 140) & (val > 90)) | (
        (sat < 45) & (val > 185)
    )
    plant = leaf_green | straw
    # Ripe head colour: warm tan / golden wheat below the straw band, where a
    # mature ear close-up actually sits (moderate saturation, hue ~21-58 deg).
    ripe = (
        (hue >= _RIPE_HUE_MIN)
        & (hue <= _RIPE_HUE_MAX)
        & (sat >= _RIPE_SAT)
        & (val >= _RIPE_VAL)
    )
    ripe_share = float(ripe.mean())

    # Upright structure: how much wider the plant is at the top than at the
    # base (a headed ear/whole plant is wide up top and narrows to a stem).
    rows = plant.sum(axis=1)
    span = np.nonzero(rows)[0]
    head_ratio = 0.0
    if span.size:
        top, bottom = int(span[0]), int(span[-1])
        quarter = max(1, (bottom - top + 1) // 4)
        upper = float(rows[top : top + quarter].mean())
        lower = float(rows[bottom - quarter + 1 : bottom + 1].mean())
        if lower:
            head_ratio = upper / lower

    return {
        "green": float(leaf_green.mean()),
        "straw": float(straw.mean()),
        "plant": float(plant.mean()),
        # Horizon test: sky-like pixels must sit in the top band AND be far
        # more common there than at the bottom (a flat texture photo has the
        # same scattered bright pixels everywhere and must not read as a field).
        "sky_top": float(sky[: max(1, hue.shape[0] // 4)].mean()),
        "sky_bottom": float(sky[hue.shape[0] // 2 :].mean()),
        "head_ratio": head_ratio,
        "coherence": _largest_component_ratio(plant),
        "ripe": ripe_share,
        # One coherent ripe-colour region rather than scattered tan specks;
        # the second blob scan is only paid for when the colour is substantial.
        "ripe_coherence": (
            _largest_component_ratio(ripe) if ripe_share >= _RIPE_MIN else 0.0
        ),
        "defocus": _smooth_share(np.asarray(image.convert("L"))),
    }


def _is_ear_closeup(
    signals: dict[str, float], wheat_evidence: bool, low_quality: bool
) -> bool:
    """Conservative evidence that a clear photo shows a wheat ear/head.

    Every indicator must hold at once: a clear photo the model established as
    wheat, substantial mature golden head colour forming one coherent region,
    a near-field (smooth/defocused) background instead of dense whole-field
    texture, no open sky, and no chance of the frame being a green leaf
    close-up. Anything short of this leaves the caller's `unclear` answer in
    place - borderline images are never forced into `wheat_ear_or_head`.
    """
    if not wheat_evidence or low_quality:
        return False
    if signals["green"] >= _LEAF_GREEN_MIN or signals["sky_top"] >= _SKY_MIN:
        return False
    if signals["ripe"] < _RIPE_MIN or signals["ripe"] < 2 * max(signals["green"], 1e-6):
        return False
    if signals["ripe_coherence"] < _COHERENCE_MIN or signals["defocus"] < _DEFOCUS_MIN:
        return False
    return True


def _classify_subject(
    signals: dict[str, float], wheat_evidence: bool, low_quality: bool = False
) -> tuple[str, str]:
    """(photo_subject, scope reason). Most specific rule first; every rule
    either has defensible evidence or falls through to a conservative answer.

    ``wheat_evidence`` is the model's own ``crop_detected == "wheat"``: a
    wheat-prefixed subject is only claimed when the model established wheat.
    ``low_quality`` marks a soft-warning run; only a clear photo may be
    identified as an ear/head by colour.

    The ripe-ear rule is consulted ONLY where the photo would otherwise be
    answered `unclear`, so no leaf, field or other-plant answer can change.
    """
    if (
        signals["plant"] >= _PLANT_MIN
        and signals["sky_top"] >= _SKY_MIN
        and signals["sky_top"] >= 2 * max(signals["sky_bottom"], 1e-6)
    ):
        # Horizon / open sky above the crop: a wider view, not a leaf close-up.
        return "whole_field_or_distant_crop", _REASON_FIELD_SKY
    if signals["straw"] >= _STRAW_MIN and signals["straw"] >= 2 * max(signals["green"], 1e-6):
        # Golden/straw head texture, never mapped to the leaf rust classes.
        if wheat_evidence:
            return "wheat_ear_or_head", _REASON_EAR_STRAW
        return "other_plant_part", _REASON_OTHER_PLANT
    if signals["plant"] < _LEAF_FILL_MIN:
        # The frame is not filled with plant material: never a leaf close-up.
        if signals["plant"] >= _PLANT_MIN:
            if wheat_evidence and signals["head_ratio"] >= _HEAD_TOP_MIN:
                return "wheat_ear_or_head", _REASON_EAR_SHAPE
            if not wheat_evidence:
                return "other_plant_part", _REASON_OTHER_PLANT
            if _is_ear_closeup(signals, wheat_evidence, low_quality):
                return "wheat_ear_or_head", _REASON_EAR_COLOUR
            return "unclear", _REASON_NOT_A_LEAF_CLOSEUP
        if _is_ear_closeup(signals, wheat_evidence, low_quality):
            # Ripe golden ear close-up: no green/straw pixel band reaches it,
            # so it used to report "not enough detail to identify the part".
            return "wheat_ear_or_head", _REASON_EAR_COLOUR
        return "unclear", _REASON_SUBJECT_UNCLEAR
    if signals["coherence"] < _COHERENCE_MIN:
        # Plant pixels in many small patches: distant crop, not one leaf.
        return "whole_field_or_distant_crop", _REASON_FIELD_PATCHES
    if signals["green"] >= _LEAF_GREEN_MIN and signals["green"] > signals["straw"]:
        if wheat_evidence:
            return "wheat_leaf", _REASON_LEAF_FILL
        return "other_plant_part", _REASON_NO_WHEAT
    if wheat_evidence:
        if _is_ear_closeup(signals, wheat_evidence, low_quality):
            return "wheat_ear_or_head", _REASON_EAR_COLOUR
        return "unclear", _REASON_NOT_A_LEAF_CLOSEUP
    return "other_plant_part", _REASON_NO_WHEAT


def _screening_scope(
    raws: list[Any], payload: Any, low_quality: bool = False
) -> dict[str, Any]:
    """Plant-part / screening-scope result for the photos being screened.

    Every photo is classified on its own; if they disagree the subject stays
    `unclear` (one clear leaf close-up is what leaf screening needs).
    ``low_quality`` marks a soft-warning run: only a clear photo may be
    identified as an ear/head from its colour.
    """
    wheat_evidence = bool(isinstance(payload, dict) and payload.get("crop_detected") == "wheat")
    subjects: list[tuple[str, str]] = []
    for raw in raws:
        if not isinstance(raw, (bytes, bytearray)):
            continue
        signals = _subject_signals(bytes(raw))
        if signals is None:
            continue
        subjects.append(_classify_subject(signals, wheat_evidence, low_quality))

    if not subjects:
        photo_subject, reasons = "unclear", [_REASON_SUBJECT_UNCLEAR]
    elif all(subject == subjects[0][0] for subject, _reason in subjects):
        photo_subject, reason = subjects[0]
        reasons = [reason]
    else:
        photo_subject, reasons = "unclear", [_REASON_SUBJECTS_MIXED]

    if photo_subject == "wheat_leaf":
        screening_scope = "leaf_screening_applicable"
    elif photo_subject == "unclear":
        screening_scope = "subject_unclear"
    else:
        screening_scope = "leaf_screening_not_applicable"
        if not wheat_evidence:
            reasons = [reason for reason in reasons if reason != _REASON_NO_WHEAT]
            reasons.append(_REASON_NO_WHEAT)
    return {
        "photo_subject": photo_subject,
        "screening_scope": screening_scope,
        "scope_reasons": reasons[:3],
    }


def _scope_fields(scope: dict[str, Any] | None) -> tuple[str, str, list[str]]:
    """Validated (photo_subject, screening_scope, scope_reasons) triple."""
    photo_subject = scope.get("photo_subject") if isinstance(scope, dict) else None
    screening_scope = scope.get("screening_scope") if isinstance(scope, dict) else None
    reasons = list(scope.get("scope_reasons") or []) if isinstance(scope, dict) else []
    if photo_subject not in PHOTO_SUBJECTS:
        photo_subject = "unclear"
    if screening_scope not in SCREENING_SCOPES:
        if photo_subject == "wheat_leaf":
            screening_scope = "leaf_screening_applicable"
        elif photo_subject == "unclear":
            screening_scope = "subject_unclear"
        else:
            screening_scope = "leaf_screening_not_applicable"
    if not reasons:
        reasons = [
            _REASON_LEAF_FILL
            if screening_scope == "leaf_screening_applicable"
            else _REASON_SUBJECT_UNCLEAR
        ]
    return photo_subject, screening_scope, reasons


def _scope_data(scope: dict[str, Any] | None) -> dict[str, Any]:
    """The public screening-scope triple carried on the Vision result data."""
    photo_subject, screening_scope, scope_reasons = _scope_fields(scope)
    return {
        "photo_subject": photo_subject,
        "screening_scope": screening_scope,
        "scope_reasons": list(scope_reasons),
    }


def _passed_raws(items: list[dict[str, Any]]) -> list[Any]:
    """Photo bytes of the screened items (missing bytes simply score None)."""
    return [item.get("raw") for item in items if isinstance(item, dict)]


def _photo_report(
    assessment_status: str,
    photo_quality: str,
    photo_subject: str,
    screening_scope: str,
    scope_reasons: list[str],
    visible_sign_category: str,
    what_is_visible: list[str],
    what_is_not_clearly_visible: list[str],
    screening_interpretation: str,
    field_checks: list[str],
    retake_guidance: str | None,
    expert_review_signs: list[str],
) -> dict[str, Any]:
    return {
        "assessment_status": assessment_status,
        "photo_subject": photo_subject,
        "screening_scope": screening_scope,
        "scope_reasons": list(scope_reasons),
        "visible_sign_category": visible_sign_category,
        "photo_quality": photo_quality,
        "what_is_visible": list(what_is_visible),
        "what_is_not_clearly_visible": list(what_is_not_clearly_visible),
        "screening_interpretation": screening_interpretation,
        "field_checks": list(field_checks),
        "retake_guidance": retake_guidance,
        "expert_review_signs": list(expert_review_signs),
    }


def _blocked_photo_report(
    quality_reasons: list[str], scope: dict[str, Any] | None = None
) -> dict[str, Any]:
    """HARD BLOCK: no model ran, so nothing was screened - retake only."""
    photo_subject, screening_scope, scope_reasons = _scope_fields(scope)
    if screening_scope != "subject_unclear":
        # A blocked photo identifies no subject, whatever the bytes look like.
        photo_subject, screening_scope = "unclear", "subject_unclear"
        scope_reasons = [_REASON_QUALITY_FAILED]
    return _photo_report(
        assessment_status="not_assessable",
        photo_quality="unusable",
        photo_subject=photo_subject,
        screening_scope=screening_scope,
        scope_reasons=scope_reasons,
        visible_sign_category="unclear",
        what_is_visible=[],
        what_is_not_clearly_visible=[
            _BLOCKED_NOT_VISIBLE,
            *_farmer_quality_reasons(quality_reasons),
        ],
        screening_interpretation=_BLOCKED_INTERPRETATION,
        field_checks=[],
        retake_guidance=_REPORT_RETAKE,
        expert_review_signs=[],
    )


def _accepted_photo_report(
    finding: str | None,
    low_quality: bool,
    quality_reasons: list[str],
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build `photo_report` for a photo the quality gate let through.

    ``finding`` is the app-safe mapped visible finding of the shipped label
    map (wheat healthy / wheat rust labels only); ``scope`` is the plant-part
    / screening-scope result. The finding is only ever surfaced when the
    photo is in ``leaf_screening_applicable`` scope - a wheat ear/head, a
    whole-field shot, another plant part or an unclear subject keep
    ``unclear`` and get the scope explanation instead, so a leaf-rust result
    can never be shown for a photo that is not a leaf close-up.
    """
    photo_subject, screening_scope, scope_reasons = _scope_fields(scope)
    in_scope = screening_scope == "leaf_screening_applicable"
    if in_scope:
        # `wheat_leaf` is claimed only for a frame-filling leaf close-up.
        photo_subject = "wheat_leaf"

    if not isinstance(finding, str) or finding not in ALLOWED_CLASSES:
        # No readable mapping (None / unsupported class): the sign is unclear.
        finding = "unclear"
    if low_quality and finding not in LOW_QUALITY_CLASSES:
        # A limited photo may only surface healthy | rust-like | unclear.
        finding = "unclear"

    if not in_scope:
        # OUT OF SCOPE: no leaf-sign finding, no leaf wording, no absence
        # claim - only what the photo shows, the scope and how to retake.
        scope_not_visible = (
            list(_EAR_NOT_VISIBLE)
            if photo_subject == "wheat_ear_or_head"
            else list(_SCOPE_NOT_VISIBLE)
        )
        if low_quality:
            assessment_status, photo_quality = "limited", "limited"
            not_visible = [*_farmer_quality_reasons(quality_reasons), *scope_not_visible]
            interpretation = _SCOPE_LIMITED_INTERPRETATION
        else:
            assessment_status, photo_quality = "assessable", "clear"
            not_visible = scope_not_visible
            interpretation = _SUBJECT_INTERPRETATION.get(
                photo_subject, _SUBJECT_UNCLEAR_INTERPRETATION
            )
        return _photo_report(
            assessment_status=assessment_status,
            photo_quality=photo_quality,
            photo_subject=photo_subject,
            screening_scope=screening_scope,
            scope_reasons=scope_reasons,
            visible_sign_category="unclear",
            what_is_visible=list(_SUBJECT_VISIBLE.get(photo_subject, _SUBJECT_UNCLEAR_VISIBLE)),
            what_is_not_clearly_visible=not_visible,
            screening_interpretation=interpretation,
            field_checks=list(_SCOPE_CHECK),
            retake_guidance=_SCOPE_RETAKE,
            expert_review_signs=[],
        )

    if finding == "healthy_looking":
        category = "healthy_looking"
        visible = _HEALTHY_VISIBLE
        not_visible = _HEALTHY_NOT_VISIBLE
        interpretation = _HEALTHY_INTERPRETATION
        checks = _HEALTHY_CHECKS
    elif finding == "rust_like_pustules":
        category = "rust_like_marks"
        visible = _RUST_VISIBLE
        not_visible = _RUST_NOT_VISIBLE
        interpretation = _RUST_INTERPRETATION
        checks = _RUST_CHECKS
    else:
        category = "unclear"
        visible = _NOT_VISIBLE_ANY
        not_visible = _NOT_CLASSIFIED
        interpretation = (
            _UNCLEAR_INTERPRETATION if finding == "unclear" else _UNCLASSIFIED_INTERPRETATION
        )
        checks = _HEALTHY_CHECKS

    if low_quality:
        assessment_status, photo_quality = "limited", "limited"
        # Never claim absence of signs from a limited photo: only the reason
        # the photo is limited, plus the standing one-photo limitation.
        not_visible = [*_farmer_quality_reasons(quality_reasons), *_LIMITED_NOT_VISIBLE]
        interpretation = _LIMITED_INTERPRETATION
        retake = _REPORT_RETAKE
    else:
        assessment_status, photo_quality = "assessable", "clear"
        retake = None

    return _photo_report(
        assessment_status=assessment_status,
        photo_quality=photo_quality,
        photo_subject=photo_subject,
        screening_scope=screening_scope,
        scope_reasons=scope_reasons,
        visible_sign_category=category,
        what_is_visible=visible,
        what_is_not_clearly_visible=not_visible,
        screening_interpretation=interpretation,
        field_checks=checks,
        retake_guidance=retake,
        expert_review_signs=_RUST_EXPERT_SIGNS if category == "rust_like_marks" else [],
    )


def _mapped_finding_from_payload(payload: dict[str, Any]) -> str | None:
    """First app-safe class the model reported, when diagnostics did not run."""
    findings = payload.get("visible_findings")
    if isinstance(findings, list):
        for item in findings:
            if isinstance(item, dict) and item.get("class") in ALLOWED_CLASSES:
                return str(item["class"])
    return None


def _diagnostics(
    quality_state: str,
    quality_reasons: list[str],
    raw: bytes | None = None,
    allow_inference: bool = True,
) -> dict[str, Any]:
    """Temporary structured diagnostics for the local ONNX pipeline.

    Carries only shapes, labels, indices and scores - never photo bytes,
    filesystem paths or secrets. ``raw=None`` (hard-blocked photo) means the
    model is neither loaded nor run.
    """
    diag: dict[str, Any] = {
        "model_loaded": False,
        "model_input_shape": None,
        "model_output_shape": None,
        "preprocess_shape": None,
        "raw_top_label": None,
        "raw_top_index": None,
        "raw_top_score": None,
        "quality_state": quality_state,
        "quality_reasons": list(quality_reasons),
        "mapped_visible_finding": None,
    }
    if raw is None:
        return diag
    try:
        bundle, _reason = vi._ensure_bundle(vi._model_dir())
    except Exception:  # noqa: BLE001 - diagnostics must never break the pipeline.
        bundle = None
    if bundle is None:
        return diag
    try:
        session = bundle["session"]
        diag["model_loaded"] = True
        diag["model_input_shape"] = list(session.get_inputs()[0].shape)
        diag["model_output_shape"] = list(session.get_outputs()[0].shape)
        if not allow_inference:
            return diag
        tensor = vi._preprocess(raw, bundle)
        if tensor is None:
            return diag
        diag["preprocess_shape"] = [int(dim) for dim in tensor.shape]
        outputs = session.run(None, {bundle["input_name"]: tensor[np.newaxis]})[0]
        logits = np.asarray(outputs, dtype=np.float32)
        row = logits.reshape(-1) if logits.ndim == 1 else logits[0]
        # The graph emits logits: one numerically stable softmax, never twice.
        exp = np.exp(row - float(row.max()))
        probs = exp / float(exp.sum())
        index = int(np.argmax(row))
        diag["raw_top_index"] = index
        diag["raw_top_label"] = bundle["id2label"].get(index)
        diag["raw_top_score"] = round(float(probs[index]), 6)
        diag["mapped_visible_finding"] = map_visible_finding(
            diag["raw_top_label"], bundle["label_map"]
        )
    except Exception:  # noqa: BLE001 - diagnostics must never break the pipeline.
        pass
    return diag


def _with_diagnostics(result: AgentResult, diagnostics: dict[str, Any]) -> AgentResult:
    """Attach the temporary diagnostics block to a Vision result's ``data``."""
    result.data["diagnostics"] = diagnostics
    return result


def _quality_state(quality: dict[str, Any]) -> str:
    """State of one photo (``clear`` | ``soft_warning`` | ``blocked``).

    Prefers the gate's own ``quality_state``; falls back to deriving it from
    the issue tiers so callers that only carry the older fields still work.
    """
    state = quality.get("quality_state")
    if state in (CLEAR, SOFT_WARNING, BLOCKED):
        return str(state)
    issues = set(quality.get("issues") or [])
    hard = set(quality.get("hard_issues") or []) | issues & {
        "too_large",
        "bad_file",
        "too_dark",
        "too_bright",
    }
    width, height = quality.get("width"), quality.get("height")
    if width and height and min(int(width), int(height)) < MIN_ACCEPT_SIDE:
        hard.add("low_resolution")
    soft = set(quality.get("soft_issues") or []) | issues - hard - {"no_plant"}
    if hard:
        return BLOCKED
    if soft:
        return SOFT_WARNING
    return CLEAR


def _fill_mapped_finding(diagnostics: dict[str, Any], payload: Any) -> None:
    """Best-effort app-safe finding when the raw label was not observed locally."""
    if diagnostics.get("mapped_visible_finding") or not isinstance(payload, dict):
        return
    findings = payload.get("visible_findings")
    first = findings[0] if isinstance(findings, list) and findings else None
    label = first.get("class") if isinstance(first, dict) else None
    if label in ALLOWED_CLASSES:
        diagnostics["mapped_visible_finding"] = label
    elif payload.get("crop_detected") != "wheat":
        # Non-wheat / unknown class: the app-safe mapping is "unclear".
        diagnostics["mapped_visible_finding"] = "unclear"


def _safe_image_bytes(raw: bytes) -> tuple[bytes, str]:
    # Re-encoding strips EXIF/GPS and normalizes orientation before private storage/inference.
    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600, 1600))
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=88, optimize=True)
        return out.getvalue(), "image/jpeg"


async def _fetch_remote_prediction(
    settings: Any, assessment_id: str, intake: dict[str, Any], passed: list[dict[str, Any]]
) -> dict[str, Any]:
    """POST quality-passed photos to the operator-configured private endpoint."""
    contents = []
    for item in passed:
        clean, mime = await asyncio.to_thread(_safe_image_bytes, item["raw"])
        contents.append(("files", (f"{item['record']['id']}.jpg", clean, mime)))
    fields = {
        "assessment_id": assessment_id,
        "crop": "wheat",
        "growth_stage": intake.get("growth_stage", "not_sure"),
        "contract_version": "kisanos-agent-v1",
    }
    headers = {"Authorization": f"Bearer {settings.vision_inference_token}"} if settings.vision_inference_token else {}
    async with httpx.AsyncClient(timeout=settings.agent_timeout_seconds, follow_redirects=False) as client:
        response = await client.post(settings.vision_inference_url, data=fields, files=contents, headers=headers)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("model response must be a JSON object")
    return payload


def _model_unavailable_result(
    assessment_id: str, passed: list[dict[str, Any]], now: datetime, reason: str
) -> AgentResult:
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="vision",
        status="unavailable",
        summary="The private vision inference service was unavailable or returned an invalid response; no model finding was accepted.",
        observations=["Photo quality checks passed; model output was not available."],
        checks=["Continue using farmer-entered symptoms or retry the private model later."],
        evidence_band="not_calibrated",
        evidence_reason=reason,
        provider_or_model="self-hosted-unavailable",
        version=VERSION,
        created_at=now,
        safety_flags=["model_unavailable", "invalid_output_rejected"],
        data={
            "quality_passed": True,
            "image_ids": [item["record"]["id"] for item in passed],
            **_scope_data(_screening_scope(_passed_raws(passed), None)),
        },
        input_evidence=["Quality-approved photos; no valid model response"],
    )


def _no_model_configured_result(
    assessment_id: str, passed: list[dict[str, Any]], now: datetime, reason: str
) -> AgentResult:
    """Safe fallback: quality passed but no model artifacts / endpoint exist."""
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="vision",
        status="not_assessed",
        summary="Photo quality passed, but no self-hosted vision model is configured; no example or simulated model result is shown.",
        observations=["At least one photo passed the supplied image-quality gate."],
        checks=["Connect the approved private vision inference service, or continue with farmer-entered symptoms."],
        evidence_band="not_calibrated",
        evidence_reason="Quality checks do not identify symptoms; inference is unavailable.",
        provider_or_model="team-vision-quality-gate; inference not configured",
        version=VERSION,
        created_at=now,
        safety_flags=["model_unavailable", "no_dummy_output_used"],
        data={
            "quality_passed": True,
            "images_accepted": len(passed),
            "image_ids": [item["record"]["id"] for item in passed],
            **_scope_data(_screening_scope(_passed_raws(passed), None)),
            "model_integration": {
                "state": "not_available",
                "plug_in_point": "app.services.vision_inference:predict_locally",
                "reason": reason,
            },
        },
        input_evidence=["Image quality gate passed; no model output"],
    )


def _accept_prediction(
    assessment_id: str,
    payload: dict[str, Any],
    passed: list[dict[str, Any]],
    now: datetime,
    low_quality: bool = False,
    mapped_finding: str | None = None,
    quality_reasons: list[str] | None = None,
    scope: dict[str, Any] | None = None,
) -> AgentResult:
    """Validate a model prediction and build the result. Fail-closed on any
    unsupported content: non-wheat crop, unsafe text, or malformed output.

    ``low_quality=True`` marks a soft-warning run: the photos only passed the
    soft tier of the quality gate, so the result is capped at status=partial,
    evidence_band/confidence=low, safe vocabulary only, and retake guidance.

    ``mapped_finding`` is the mapped visible finding observed by the local
    pipeline, ``quality_reasons`` the gate's own reasons for a soft-warning
    run and ``scope`` the plant-part / screening-scope result; all three feed
    the farmer-facing ``photo_report``. When ``scope`` is not passed it is
    derived from the screened photos here, so the caller cannot forget it.
    """
    if not isinstance(scope, dict):
        scope = _screening_scope(_passed_raws(passed), payload, low_quality)
    photo_subject, screening_scope, _scope_reasons = _scope_fields(scope)
    in_scope = screening_scope == "leaf_screening_applicable"
    crop_detected = payload.get("crop_detected")
    if crop_detected != "wheat":
        status = "unsupported" if crop_detected else "unavailable"
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status=status,
            summary="The vision result did not establish a supported wheat photo; no visible symptom finding was accepted.",
            evidence_reason="The private model must return crop_detected='wheat'; missing or unsupported crop output abstains.",
            provider_or_model="self-hosted-rejected",
            version=VERSION,
            created_at=now,
            safety_flags=["wheat_scope_gate", "no_interpretation_accepted"],
            checks=[_SCOPE_RETAKE],
            data={
                "quality_passed": True,
                "image_ids": [item["record"]["id"] for item in passed],
                **_scope_data(scope),
            },
            input_evidence=["Quality-approved photos; crop check not passed"],
        )
    findings = payload.get("visible_findings", [])
    if low_quality:
        # Low-confidence screening: only healthy | rust-like may surface;
        # anything else collapses to "unclear" below. Never disease language.
        findings = [
            finding
            for finding in findings
            if isinstance(finding, dict) and finding.get("class") in LOW_QUALITY_CLASSES
        ]
    observations, seen = [], set()
    # The mapped finding feeds `photo_report`; take the local pipeline's value
    # when it ran, else the first app-safe class the model reported.
    mapped = (
        mapped_finding
        if mapped_finding in ALLOWED_CLASSES
        else _mapped_finding_from_payload(payload)
    )
    for finding in findings[:8]:
        label = finding.get("class") if isinstance(finding, dict) else None
        if label not in ALLOWED_CLASSES:
            continue
        detail = str(finding.get("detail", "visible sign noted"))[:180]
        if UNSAFE_MODEL_TEXT.search(detail):
            return AgentResult(
                assessment_id=assessment_id,
                agent_id="vision",
                status="unavailable",
                summary="The model response did not pass the safety gate; no visual interpretation was accepted.",
                evidence_reason="A model output contained unsupported diagnostic or action language and was rejected.",
                provider_or_model="self-hosted-rejected",
                version=VERSION,
                created_at=now,
                safety_flags=["unsafe_model_text_rejected", "no_interpretation_accepted"],
                data={"quality_passed": True, "image_ids": [item["record"]["id"] for item in passed]},
                input_evidence=["Quality-approved photos; model response rejected"],
            )
        safe = f"{LABELS[label]}: {detail}"
        if safe not in seen:
            observations.append(safe)
            seen.add(safe)
    if not observations:
        if low_quality:
            observations = [LABELS["unclear"]]
        else:
            observations = ["The model did not return a supported visible finding."]
    if not in_scope:
        # OUT OF SCOPE: model-derived observations would read as a leaf
        # finding. One neutral scope sentence is all that may travel - it is
        # also what Crop sees as photo evidence (its finding stays "unclear").
        observations = [
            _SUBJECT_OBSERVATION.get(photo_subject, _SUBJECT_OBSERVATION["unclear"])
        ]
    photo_report = _accepted_photo_report(
        mapped, low_quality, list(quality_reasons or []), scope
    )
    if low_quality:
        # Soft-warning policy: preliminary, low-confidence screening only.
        quality_issues = sorted(
            {issue for item in passed for issue in item["quality"].get("issues", [])}
        )
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status="partial",
            summary=(
                "Photo quality is limited. This is a low-confidence visible-sign "
                "screening result; retake a clearer close-up if possible."
            ),
            observations=observations,
            possible_causes=[],
            checks=[
                "Retake a clearer close-up in daylight with the affected leaf in focus.",
                "Compare the visible pattern on several plants and inspect both sides of affected leaves.",
            ],
            evidence_band="low",
            evidence_reason=(
                "Low-quality image: low-confidence screening only; the evidence band "
                "and confidence are capped at low, and no cause is established."
            ),
            sources=[
                Source(
                    title="Self-hosted KisanOS vision inference",
                    publisher="Configured private model service",
                    source_status="unverified",
                    note="Model artifact and locally validated performance must be recorded by deployment.",
                )
            ],
            provider_or_model="self-hosted",
            version=str(payload.get("model_version", VERSION))[:80],
            created_at=now,
            safety_flags=[
                "low_quality_image",
                "low_confidence",
                "retake_recommended",
                "not_a_diagnosis",
            ],
            data={
                "quality_passed": False,
                "low_quality": True,
                "confidence": "low",
                "quality_issues": quality_issues,
                "photo_report": photo_report,
                **_scope_data(scope),
                "images_accepted": len(passed),
                "image_ids": [item["record"]["id"] for item in passed],
                "model_version": str(payload.get("model_version", "not reported"))[:80],
            },
            input_evidence=[
                "Image quality warning: low-quality photo used only for low-confidence visible-sign screening",
                *[f"Quality issue: {issue.replace('_', ' ')}" for issue in quality_issues],
            ],
        )
    # The model is uncalibrated locally: confidence is capped at medium and never a disease probability.
    evidence_band = "medium" if len(passed) >= 2 and payload.get("confidence") == "medium" else "low"
    return AgentResult(
        assessment_id=assessment_id,
        agent_id="vision",
        status="complete",
        summary="Photos can describe visible signs only and cannot confirm their cause.",
        observations=observations,
        possible_causes=[],
        checks=(
            list(_SCOPE_CHECK)
            if not in_scope
            else ["Compare the visible pattern on several plants and inspect both sides of affected leaves."]
        ),
        evidence_band=evidence_band,
        evidence_reason="Uncalibrated self-hosted model output; evidence band describes image evidence quality, not disease probability. Confidence is capped at medium.",
        sources=[
            Source(
                title="Self-hosted KisanOS vision inference",
                publisher="Configured private model service",
                source_status="unverified",
                note="Model artifact and locally validated performance must be recorded by deployment.",
            )
        ],
        provider_or_model="self-hosted",
        version=str(payload.get("model_version", VERSION))[:80],
        created_at=now,
        safety_flags=["not_a_diagnosis", "local_validation_pending", "confidence_capped_at_medium"],
        data={
            "quality_passed": True,
            # Model confidence, reported separately from the (clear) quality state.
            "confidence": evidence_band,
            "photo_report": photo_report,
            **_scope_data(scope),
            "images_accepted": len(passed),
            "image_ids": [item["record"]["id"] for item in passed],
            "model_version": str(payload.get("model_version", "not reported"))[:80],
        },
        input_evidence=["Quality-approved uploaded wheat photos"],
    )


async def analyze_images(
    assessment_id: str, intake: dict[str, Any], image_records: list[dict[str, Any]]
) -> AgentResult:
    now = datetime.now(UTC)
    if not image_records:
        no_photo = AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status="not_assessed",
            summary="Vision was not assessed because no photo was supplied.",
            evidence_reason="No image evidence.",
            provider_or_model="not_configured",
            version=VERSION,
            created_at=now,
            safety_flags=["manual_fallback_available"],
            data=_scope_data(
                {
                    "photo_subject": "unclear",
                    "screening_scope": "subject_unclear",
                    "scope_reasons": [_REASON_NO_PHOTO],
                }
            ),
            input_evidence=["No photos supplied"],
        )
        return _with_diagnostics(
            no_photo,
            _diagnostics(BLOCKED, ["no_image_supplied"]),
        )

    checked = []
    failures = []
    for record in image_records[:4]:
        try:
            raw = await asyncio.to_thread(record["read_bytes"])
            quality = await asyncio.to_thread(check_quality, raw)
            checked.append({"record": record, "raw": raw, "quality": quality})
            if not quality.get("passed"):
                failures.extend(quality.get("issues", []))
        except (OSError, KeyError, TypeError):
            failures.append("image_unreadable")

    states = [(item, _quality_state(item["quality"])) for item in checked]
    # Soft tier: a decodable >=96 px photo carrying only a warning still runs
    # the model - a soft warning never prevents inference. Quality state and
    # model confidence stay separate: a clear photo may still score low.
    runnable = [item for item, state in states if state != BLOCKED]
    has_clear = any(state == CLEAR for _item, state in states)
    if not runnable:
        run_state = BLOCKED
    elif has_clear:
        run_state = CLEAR
    else:
        run_state = SOFT_WARNING
    low_quality = run_state == SOFT_WARNING

    if run_state == BLOCKED:
        quality_reasons = sorted(
            {
                issue
                for item, state in states
                if state == BLOCKED
                for issue in item["quality"].get("hard_issues", [])
            }
        ) or sorted(set(failures))
        # HARD BLOCK: corrupt / unreadable / <96 px / near-black / near-white.
        # The model is NOT loaded or run; no disease or stress inference.
        blocked = AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status="not_assessed",
            summary="No uploaded photo passed the image-quality checks; no visual interpretation was made.",
            observations=[f"Photo quality issue: {issue.replace('_', ' ')}" for issue in sorted(set(failures))],
            checks=[
                "Retake a close-up in daylight with the affected plant part in focus, or continue using farmer-entered observations."
            ],
            evidence_band="not_calibrated",
            evidence_reason="The uploaded image(s) failed the supplied team's quality gate.",
            provider_or_model="team-vision-quality-gate",
            version=VERSION,
            created_at=now,
            safety_flags=["photo_quality_failed", "no_visual_analysis_performed"],
            data={
                "quality_passed": False,
                "quality_issues": sorted(set(failures)),
                "photo_report": _blocked_photo_report(quality_reasons, BLOCKED_SCOPE),
                **_scope_data(BLOCKED_SCOPE),
                "image_ids": [item["record"]["id"] for item in checked],
            },
            input_evidence=["Uploaded photos did not pass image-quality checks"],
        )
        return _with_diagnostics(blocked, _diagnostics(run_state, quality_reasons))

    if run_state == SOFT_WARNING:
        quality_reasons = sorted(
            {
                issue
                for item in runnable
                for issue in item["quality"].get("soft_issues", [])
            }
        )
    else:
        quality_reasons = []

    settings = get_settings()
    remote = bool(settings.vision_inference_url)
    # Temporary diagnostics: shapes + raw top-1 of the first runnable photo.
    diagnostics = _diagnostics(
        run_state,
        quality_reasons,
        raw=runnable[0]["raw"],
        allow_inference=not remote,
    )

    if remote:
        # The only path that receives images is an operator-configured private self-hosted endpoint.
        try:
            payload = await _fetch_remote_prediction(settings, assessment_id, intake, runnable)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, OSError):
            return _with_diagnostics(
                _model_unavailable_result(
                    assessment_id,
                    runnable,
                    now,
                    "Service error or schema mismatch; output safely abstained.",
                ),
                diagnostics,
            )
    else:
        # Local ONNX plug-in point (app.services.vision_inference).
        # Missing artifacts return (None, reason) and Vision stays in safe
        # fallback - never a dummy or example result.
        try:
            payload, reason = predict_locally([item["raw"] for item in runnable], intake)
        except Exception:  # noqa: BLE001 - a broken loader must never crash the pipeline.
            payload, reason = None, "local model inference raised an unexpected error; no result was used"
        if payload is None:
            return _with_diagnostics(
                _no_model_configured_result(
                    assessment_id, runnable, now, reason or "local model inference is not configured"
                ),
                diagnostics,
            )
    _fill_mapped_finding(diagnostics, payload)
    # Plant-part / screening-scope result, derived from the photos themselves.
    scope = _screening_scope(_passed_raws(runnable), payload, low_quality)
    if scope["screening_scope"] != "leaf_screening_applicable":
        # The label map's wheat leaf class must not travel as a public finding
        # when the photo is not a leaf close-up; the raw label stays in
        # `diagnostics` as technical data only.
        diagnostics["mapped_visible_finding"] = "unclear"

    try:
        result = _accept_prediction(
            assessment_id,
            payload,
            runnable,
            now,
            low_quality=low_quality,
            mapped_finding=diagnostics.get("mapped_visible_finding"),
            quality_reasons=quality_reasons,
            scope=scope,
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        result = _model_unavailable_result(
            assessment_id,
            runnable,
            now,
            "Service error or schema mismatch; output safely abstained.",
        )
    return _with_diagnostics(result, diagnostics)

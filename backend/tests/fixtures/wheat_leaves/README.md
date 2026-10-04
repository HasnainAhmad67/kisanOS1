# Wheat leaf test fixtures

Real, openly licensed wheat photos used by `tests/test_vision_model.py` and the
end-to-end smoke test. **No synthetic or simulated findings**: every fixture is
an original photograph from iNaturalist, and each one was selected by

1. visually inspecting the photo (subject and symptoms confirmed by eye), and
2. running the shipped local model (`backend/models/wheat_vision/`) on it and
   recording its top-1 prediction.

| Fixture | Source observation | Photographer | License | Visually | Model top-1 (recorded 2026-10-04) |
|---|---|---|---|---|---|
| `healthy_leaf.jpg` | https://www.inaturalist.org/observations/365721187 | iNaturalist user `ohwhen` | CC BY 4.0 | Healthy green wheat plants, no visible symptoms | `Wheat___Healthy` p=0.97 → `healthy_looking` |
| `brown_rust_leaf.jpg` | https://www.inaturalist.org/observations/191315663 | iNaturalist user `zihaowang` | CC BY 4.0 | Wheat leaf with orange-brown rust pustules (leaf/brown rust, *Puccinia rubigo-vera* / *P. triticina*) | `Wheat___Brown_Rust` p=0.60 → `rust_like_pustules` |
| `yellow_rust_leaf.jpg` | https://www.inaturalist.org/observations/161111587 | iNaturalist user `dvid_horvath` | CC BY 4.0 | Wheat leaf with a yellow-orange stripe of pustules (stripe/yellow rust, *Puccinia striiformis*) | `Wheat___Brown_Rust` p=0.82 → `rust_like_pustules` |

Honesty notes:

* `yellow_rust_leaf.jpg` is genuinely stripe (yellow) rust by identification,
  but the model's internal top-1 label is `Wheat___Brown_Rust`. Both wheat rust
  classes map to the same KisanOS visible class `rust_like_pustules`, so the
  fixture is used to assert exactly that mapping — the internal label
  disagreement is recorded here rather than hidden.
* The publisher's model is uncalibrated on these photos; probabilities above
  are recorded only as provenance for how the fixtures were chosen, never as
  disease confidence (the pipeline caps confidence at `medium` and reports it
  as image-evidence quality only).
* Originals were resized so the short side is 800 px (the independent image
  quality gate requires ≥ 640 px) and re-encoded as JPEG (quality 88). At this
  size all three pass `check_quality` (blur ≥ 100, brightness 40–220, plant
  fraction ≥ 0.10) and the model predictions above still hold.

License compliance: CC BY 4.0 requires attribution — the table above is the
attribution; keep it with the images when redistributing.

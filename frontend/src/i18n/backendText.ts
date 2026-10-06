/**
 * Deterministic backend prose → Urdu.
 *
 * The backend always answers in English. Only *known, fixed* sentences are
 * translated here (exact string equality or an exact `"<label>: <detail>"`
 * prefix split) — arbitrary backend paragraphs are never machine-translated
 * or string-replaced. Anything that does not match is shown by
 * `<BackendText>` as English under the visible label
 * "اصل نظامی پیغام (English)" so safety-critical wording is never hidden.
 *
 * `backendUr` is typed `Record<BackendTextKey, string>`, so a missing Urdu
 * entry is a TypeScript error — same guarantee as en.ts/ur.ts.
 */

/** Exact English sentences produced by the deterministic agents. */
export const backendEn = {
  /* ------------------------------------------------ farm plan (advisor) */
  "plan.how.crop":
    "Repeat the check on several plants in the affected area and on one healthy-looking area for comparison.",
  "plan.how.water":
    "Check the same spots by hand at root depth and compare the affected and unaffected areas.",
  "plan.how.vision":
    "Look at the plant part described in the report and compare it with a healthy-looking plant.",
  "plan.how.farm_advisor":
    "Describe the plant part and compare several plants with a healthy-looking area.",
  "plan.what_to_observe":
    "What you actually see at each spot, whether it looks the same on plants that look healthy, and whether it changes between checks.",
  "plan.why.crop":
    "Farmer-reported and/or photo-visible evidence; possibilities remain unconfirmed.",
  "plan.why.water":
    "Conservative soil and drainage check; no irrigation schedule or command is inferred.",
  "plan.why.vision":
    "Image evidence is limited to visible signs and cannot confirm cause.",
  "plan.why.vision_low_quality":
    "The photo was low-quality; the visible-sign check is low-confidence only.",
  "plan.why.insufficient": "There is not enough evidence to distinguish a cause.",
  "plan.rationale.expert":
    "Spreading, rust-like, severe, or unclear symptoms merit review by a qualified local expert; the system does not identify a confirmed cause.",
  "plan.rationale.insufficient":
    "Key field or symptom information is missing or uncertain; the system does not infer a normal/abnormal verdict.",
  "plan.rationale.field_inspection":
    "Available reports support a small set of direct field checks; they do not establish a cause or prescribe an action.",
  "plan.rationale.monitor":
    "Continue observing the field and update the assessment if signs change.",
  "plan.verification_step":
    "Record what you observed after checking; if signs spread, remain unclear, or appear severe, ask a local agriculture officer to review them.",
  "plan.fallback_check":
    "Describe which plant part looks different and compare several plants with a healthy-looking area.",
  "plan.how.escalation":
    "Share what you recorded with a local agriculture officer or qualified expert and follow their guidance.",
  "plan.escalation.fallback":
    "Ask a local agriculture officer or qualified expert to review these signs before any action.",
  "plan.check.vision_cross":
    "Inspect several leaves on the photographed plant and nearby plants, including both leaf surfaces, for spots, yellowing, rust-like marks, or insects.",

  /* ---------------------------------------------------------- conflicts */
  "conflict.wet_soil":
    "Farmer reports wet soil or drainage concern",
  "conflict.overlap_water_stress":
    "Crop Agent identified signs that can overlap with water stress",
  "conflict.wet_soil_next":
    "Compare root-zone moisture in affected and unaffected spots; wet soil does not rule out other causes.",
  "conflict.dry_soil":
    "Farmer reports dry soil at the observed time",
  "conflict.dry_vs_rain_next":
    "Compare the observation time with the weather timestamp and re-check soil moisture by hand at root depth in affected and unaffected spots.",
  "conflict.stale_weather":
    "Weather provider timestamp is stale or missing",
  "conflict.stale_weather_next":
    "Do not use this weather result for a field decision; continue with direct field checks.",
  "conflict.crop_vision_next":
    "Compare the photo-visible signs with what you reported in the field on several plants, and ask a local agriculture officer to review anything that keeps disagreeing.",

  /* ------------------------------------------------------------- vision */
  "vision.summary.model_unavailable":
    "The private vision inference service was unavailable or returned an invalid response; no model finding was accepted.",
  "vision.summary.no_model":
    "Photo quality passed, but no self-hosted vision model is configured; no example or simulated model result is shown.",
  "vision.summary.scope_gate":
    "The vision result did not establish a supported wheat photo; no visible symptom finding was accepted.",
  "vision.summary.unsafe_text":
    "The model response did not pass the safety gate; no visual interpretation was accepted.",
  "vision.summary.soft_warning":
    "Photo quality is limited. This is a low-confidence visible-sign screening result; retake a clearer close-up if possible.",
  "vision.summary.complete":
    "Photos can describe visible signs only and cannot confirm their cause.",
  "vision.summary.no_photo": "Vision was not assessed because no photo was supplied.",
  "vision.summary.blocked":
    "No uploaded photo passed the image-quality checks; no visual interpretation was made.",
  "vision.obs.model_output_missing":
    "Photo quality checks passed; model output was not available.",
  "vision.obs.gate_passed":
    "At least one photo passed the supplied image-quality gate.",
  "vision.obs.no_finding":
    "The model did not return a supported visible finding.",
  "vision.check.continue_farmer":
    "Continue using farmer-entered symptoms or retry the private model later.",
  "vision.check.connect_service":
    "Connect the approved private vision inference service, or continue with farmer-entered symptoms.",
  "vision.check.retake_daylight":
    "Retake a clearer close-up in daylight with the affected leaf in focus.",
  "vision.check.retake_or_farmer":
    "Retake a close-up in daylight with the affected plant part in focus, or continue using farmer-entered observations.",
  "vision.check.compare_plants":
    "Compare the visible pattern on several plants and inspect both sides of affected leaves.",
  "vision.reason.no_evidence": "No image evidence.",
  "vision.reason.quality_failed":
    "The uploaded image(s) failed the supplied team's quality gate.",
  "vision.reason.gate_identifies":
    "Quality checks do not identify symptoms; inference is unavailable.",
  "vision.reason.soft_low_confidence":
    "Low-quality image: low-confidence screening only; the evidence band and confidence are capped at low, and no cause is established.",
  "vision.reason.uncalibrated":
    "Uncalibrated self-hosted model output; evidence band describes image evidence quality, not disease probability. Confidence is capped at medium.",
  "vision.reason.scope_gate":
    "The private model must return crop_detected='wheat'; missing or unsupported crop output abstains.",
  "vision.reason.unsafe_text":
    "A model output contained unsupported diagnostic or action language and was rejected.",

  /* ------------------------------ vision: photo screening report strings */
  "vision.report.retake":
    "Take a clear close-up photo of one affected leaf in daylight, with the leaf filling most of the frame.",
  "vision.report.visible.leaf_even": "Leaf surface appears generally even in colour.",
  "vision.report.visible.no_rust":
    "No clear rust-like raised marks are visible in this photo.",
  "vision.report.visible.no_spots":
    "No large distinct spots are clearly visible in this photo.",
  "vision.report.interp.healthy":
    "This photo does not show clear visible warning signs. A single photo cannot rule out problems elsewhere in the field.",
  "vision.report.checks.both_sides":
    "Inspect both sides of several leaves in this area for any marks or spots.",
  "vision.report.checks.compare_plants":
    "Compare this plant with a few nearby plants in the same field.",
  "vision.report.visible.rust_marks":
    "Scattered orange-brown round marks are visible on the leaf surface.",
  "vision.report.not_visible.cause": "The cause of these marks cannot be seen in a photo.",
  "vision.report.interp.rust":
    "Rust-like visible signs may be present. The cause is not confirmed from a photo alone.",
  "vision.report.checks.rust_1":
    "Inspect both sides of 5–10 affected leaves for raised orange, yellow, or brown marks.",
  "vision.report.checks.rust_2": "Compare affected plants with nearby healthy-looking plants.",
  "vision.report.checks.rust_3": "Check whether newer leaves are becoming affected.",
  "vision.report.expert.spread": "Marks spread quickly",
  "vision.report.expert.new_leaves": "New leaves become affected",
  "vision.report.expert.larger_area": "A larger part of the field is affected",
  "vision.report.interp.unclear":
    "Photo quality was adequate, but the visible sign could not be classified by this screening model.",
  "vision.report.interp.unclassified":
    "Photo quality was adequate, but the visible sign reported on the photo is not one of the healthy-looking or rust-like signs this screening reports.",
  "vision.report.visible.leaf_seen": "A plant leaf is visible in the photo.",
  "vision.report.not_visible.unknown_sign":
    "This screening could not say which visible sign is present.",
  "vision.report.interp.limited":
    "A preliminary visible-sign screening was still performed on this photo. Because the photo quality is limited, this photo cannot rule out visible signs.",
  "vision.report.not_visible.elsewhere":
    "A single photo cannot show conditions elsewhere in the field.",
  "vision.report.interp.blocked":
    "No uploaded photo passed the photo-quality checks, so no visible-sign screening was performed.",
  "vision.report.not_visible.nothing":
    "No photo could be reviewed, so nothing was checked.",
  "vision.quality.too_large": "The photo file is too big. Please send a photo under 10 MB.",
  "vision.quality.bad_file":
    "This file could not be opened as a photo. Please send a JPG or PNG.",
  "vision.quality.low_resolution":
    "The photo is too small. Please take it with the normal camera at full quality.",
  "vision.quality.blurry":
    "The photo is blurry. Hold the phone steady and tap the leaf to focus.",
  "vision.quality.too_dark": "The photo is too dark. Please take it in daylight.",
  "vision.quality.too_bright":
    "The photo is too bright or has glare. Please avoid direct sun on the camera.",
  "vision.quality.no_plant":
    "No crop is visible. Please move closer so the leaves fill most of the photo.",
  "vision.quality.image_unreadable":
    "This photo could not be read. Please send a JPG or PNG photo.",
  "vision.quality.no_image_supplied":
    "No photo was supplied, so nothing could be checked.",

  /* --------------- vision: plant part / screening scope (leaf vs ear) */
  "vision.scope.leaf_fill":
    "The photo is a close-up that fills the frame with leaf material, so leaf-sign screening applies.",
  "vision.scope.ear_straw":
    "Golden straw-coloured head texture fills the frame, so this photo shows a wheat ear/head rather than a leaf.",
  "vision.scope.ear_shape":
    "The photo shows an upright wheat plant against a background instead of a leaf close-up, so it shows an ear/head rather than a leaf.",
  "vision.scope.ear_ripe":
    "The photo is a clear close-up filled with mature golden wheat head colour rather than leaf material, so it shows an ear/head rather than a leaf.",
  "vision.scope.field_sky":
    "A horizon and open sky are visible, so this is a wider field view rather than a leaf close-up.",
  "vision.scope.field_patches":
    "The crop appears as many small separate patches rather than one close-up, so this is a wider field view.",
  "vision.scope.not_leaf":
    "The frame does not fill with leaf material, so leaf-sign screening was not applied.",
  "vision.scope.other_plant":
    "Plant material is visible, but this photo does not show a close-up wheat leaf.",
  "vision.scope.no_wheat":
    "Wheat was not established from this photo, so wheat leaf screening was not applied.",
  "vision.scope.subject_unclear":
    "The photo does not show enough detail to identify the plant part.",
  "vision.scope.mixed":
    "The photos do not all show the same subject; one clear close-up of a single affected leaf is needed.",
  "vision.scope.quality_failed":
    "No photo passed the quality checks, so the photo subject could not be identified.",
  "vision.scope.no_photo":
    "No photo was supplied, so the photo subject could not be identified.",
  "vision.report.not_visible.scope": "Leaf symptoms cannot be assessed from this photo.",
  "vision.report.checks.scope":
    "Inspect the leaves on this plant and a few nearby plants for any marks or spots.",
  "vision.report.retake.scope":
    "Take a clear daylight close-up of one affected leaf, with the leaf filling most of the frame.",
  "vision.report.visible.ear": "A mature wheat ear/head is visible in this photo.",
  "vision.report.not_visible.ear":
    "Leaf symptoms cannot be assessed because this image does not show a close-up leaf.",
  "vision.report.interp.ear": "This is a clear photo of a mature wheat ear/head, not a leaf.",
  "vision.report.visible.field": "Crop context is visible across the field in this photo.",
  "vision.report.interp.field":
    "This image is clear, but it shows the crop from a distance. Leaf-level symptoms cannot be assessed from a whole-field or distant photo.",
  "vision.report.visible.other_plant":
    "Plant material is visible, but it is not a close-up wheat leaf.",
  "vision.report.interp.other_plant":
    "This photo does not show a close-up wheat leaf, so leaf-sign screening was not applied.",
  "vision.report.visible.subject_unclear": "The subject of this photo could not be identified clearly.",
  "vision.report.interp.subject_unclear":
    "The photo subject could not be identified, so leaf-sign screening was not applied.",
  "vision.report.interp.scope_limited":
    "The photo quality is limited, and this screening is designed for close-up leaf signs, so leaf symptoms were not assessed from this photo.",
  "vision.report.obs.ear":
    "Wheat ear/head visible in the photo; leaf-sign screening was not applied.",
  "vision.report.obs.field":
    "Crop visible from a distance in the photo; a close-up of one affected leaf is needed.",
  "vision.report.obs.other_plant":
    "Plant material visible in the photo, but it is not a close-up wheat leaf.",

  /* ----------------------------------------------------- weather / crop */
  "weather.summary.context":
    "Weather values are provider-reported forecast-grid context, not field measurements.",
  "weather.summary.unavailable":
    "Weather data is unavailable; other assessment agents continue without weather-driven rules.",
  "weather.obs.no_values":
    "Provider response contained no current values that passed validation.",
  "weather.obs.no_rain_24h":
    "No meaningful precipitation is currently forecast in the next 24 hours; confirm field moisture before any water decision.",
  "weather.obs.rain_24h":
    "Precipitation is forecast, but it does not confirm effective root-zone recharge.",
  "weather.obs.grid_context":
    "Forecast values are grid context, not measurements from this field.",
  "weather.obs.no_24h_series":
    "The provider returned no next-24-hour precipitation series, so no rainfall statement is made.",
  "crop.summary.unsupported":
    "The Crop Agent supports wheat only; no crop assessment was made for this crop.",
  "crop.check.unsupported":
    "Select wheat, or ask a local agriculture expert about this crop.",
  "crop.summary.insufficient":
    "There is not enough symptom evidence to distinguish possible causes.",
  "crop.summary.screening":
    "The findings below are screening possibilities only; similar visible changes can have different causes.",

  /* ------------------------------------------------------------ market */
  "market.check.enter_quote":
    "Enter a recent market quote, or ask your local market committee for the current rate.",
  "market.check.ask_rate":
    "Ask your local market committee or arhti for today's rate before relying on this number.",
  "market.check.confirm_unit":
    "Confirm the unit and grade with the person who reported the quote.",
  "market.check.real_quote":
    "Use a real observed quote for anything beyond a demo; this one is simulated.",
  "market.check.confirm_all":
    "Confirm the quote, unit, market, and observation date with the source before relying on it.",
  "market.obs.farmer_reported":
    "Farmer reported this quote; KisanOS did not retrieve or verify it.",
  "market.reason.no_quote":
    "No market quote was retrieved or provided; no price is inferred.",

  /* ------------------------------------- official AMIS (Punjab) results */
  "market.summary.amis_missing_bahawalpur":
    "Price unavailable: No verified Bahawalpur wheat quote was returned by AMIS today.",
  "market.summary.amis_unreachable":
    "Price unavailable: the official AMIS price page could not be reached, so no verified quote is available today.",
  "market.summary.amis_unusable":
    "Price unavailable: AMIS did not return a usable wheat quote today.",
  "market.obs.amis_retrieved":
    "Retrieved from Punjab AMIS; KisanOS did not edit, estimate, or infer any price.",
  "market.obs.amis_stale":
    "The AMIS source date is older than 24 hours, so this quote is not labelled as current.",
  "market.obs.amis_no_date": "AMIS returned no source date for this quote.",
  "market.obs.amis_only_farmer":
    "Punjab AMIS did not return a usable quote today, so only the farmer-entered quote is shown.",
  "market.reason.amis_fresh":
    "Source-reported quote from Punjab AMIS; freshness is derived from the AMIS source date and KisanOS did not alter, estimate, or infer any price.",
  "market.reason.amis_stale":
    "Punjab AMIS source date is older than 24 hours; the quote is shown as stale and is not presented as current.",
  "market.reason.amis_no_date":
    "Punjab AMIS returned no source date; the quote is shown as source-reported with the date unavailable, not as today's price.",
  "market.check.amis_confirm":
    "Confirm the unit and grade with the mandi before you compare this quote with another rate.",

  /* ------------------------------------- crop: farmer/photo observations */
  "crop.obs.yellowing": "visible yellowing reported by the farmer",
  "crop.obs.spots": "spots or blotches reported by the farmer",
  "crop.obs.rust_like": "rust-like marks reported by the farmer",
  "crop.obs.wilting": "wilting or leaf rolling reported by the farmer",
  "crop.obs.drying": "premature drying reported by the farmer",
  "crop.obs.insects": "visible insects reported by the farmer",
  "crop.obs.mildew_like": "mildew-like appearance reported by the farmer",
  "crop.obs.lodging": "lodging reported by the farmer",
  "crop.obs.unknown": "the farmer is unsure what the symptom may be",

  /* --------------------------------------- crop: farmer-answerable checks */
  "crop.check.older_younger":
    "Compare older and younger leaves and note whether the change starts on the old or the new leaves.",
  "crop.check.uniform_patchy":
    "Check whether the pattern is uniform across the field or patchy.",
  "crop.check.both_sides":
    "Inspect both sides of several affected leaves: note the shape and colour of any spots, where they sit on the leaf, and whether both leaf surfaces are affected.",
  "crop.check.rolling_wilting":
    "Note whether leaves are rolling or plants are wilting, and whether they recover overnight.",
  "crop.check.insects":
    "Look under leaves and around the plant base, and record whether insects are visible on several plants.",
  "crop.check.irrigation_rain":
    "Ask whether the field was irrigated or received rain recently, and whether symptoms changed afterwards.",
  "crop.check.spreading":
    "Mark the edge of the affected patch and record whether symptoms are spreading from the edge inward or in scattered spots across the field.",
  "crop.check.inspect_plants":
    "Inspect several plants across the field and compare affected parts with healthy-looking parts.",
  "crop.check.describe_pattern":
    "Describe which plant part looks different and whether the pattern is uniform or patchy.",
  "crop.check.compare_healthy":
    "Compare several affected plants with a healthy-looking area.",
  "crop.check.root_zone":
    "Check root-zone soil moisture, drainage, and roots before attributing a cause.",
  "crop.check.compare_dry":
    "Compare dry plants with healthy-looking plants at several locations.",
  "crop.check.dry_origin":
    "Record whether the drying starts from leaf tips, leaf margins, or whole leaves.",
  "crop.check.patches":
    "Compare affected and unaffected patches at several locations.",
  "crop.check.rust_1":
    "Inspect both sides of 5–10 affected leaves and record whether raised orange, yellow, or brown marks are present.",
  "crop.check.rust_2":
    "Compare affected plants with nearby healthy-looking plants and note whether marks are scattered or arranged in lines.",
  "crop.check.rust_3": "Check whether newer leaves are becoming affected.",
  "crop.check.photo_discrepancy":
    "The uploaded photo did not show clear visible signs, while the farmer reported symptoms. Check multiple affected plants; the photo does not rule out a field problem.",
  "crop.check.photo_limit":
    "The uploaded photo did not show readable details, so no visible sign was read from it; this limits the photo evidence only and says nothing about the field.",
  "crop.photo.ear_scope":
    "A wheat ear/head is visible in the photo. The image does not show leaf symptoms for screening.",
  "crop.check.referral":
    "Ask a local agriculture officer or qualified expert to review spreading, rust-like, severe, or unclear symptoms before any action.",

  /* ------------------------------------------ crop: screening possibilities */
  "crop.poss.water_stress": "Possible water stress",
  "crop.poss.nutrient_stress": "Possible nutrient stress",
  "crop.poss.premature_drying": "Premature drying; multiple causes possible",
  "crop.poss.rust_symptoms": "Rust-like symptoms",
  "crop.poss.leaf_spots": "Possible leaf spots or disease",
  "crop.poss.insect_damage": "Possible insect damage",
  "crop.poss.rust":
    "Rust-like leaf signs need field verification; the cause is not confirmed.",
  "crop.poss.no_distinction": "No cause is distinguished by the available evidence",
  "crop.poss.cannot_assess": "Cause cannot be assessed from the information provided",

  /* --------------------------------------------------- crop: escalation signs */
  "crop.escalation.rust":
    "Seek local expert review if marks spread quickly, appear on new leaves, or affect a larger part of the field.",
  "crop.escalation.spreading":
    "Seek local expert review if the affected area keeps spreading quickly or new plants become affected.",
  "crop.escalation.conflict":
    "Ask a local agriculture officer to review signs that do not fit together before any action.",
  "crop.escalation.stage":
    "Ask a local agriculture officer to review symptoms seen at the heading-to-grain stages.",
  "crop.escalation.chemical":
    "Ask a local agriculture officer to answer any product or input question before acting.",
  "crop.escalation.unclear":
    "Ask a local agriculture officer to review unclear or severe-looking signs before any action.",

  /* ------------------------------------------------ water: field checks */
  "water.check.soil_moisture":
    "Check root-zone soil by hand at 3–5 representative places; compare affected and healthy-looking areas.",
  "water.check.drainage_paths":
    "Check for standing water, blocked outlets, and whether the soil remains saturated after irrigation/rain.",
  "water.check.after_rain":
    "After rainfall is actually observed, re-check root-zone soil moisture; do not treat the forecast as proof of recharge.",
  "water.check.pmd_update":
    "Check the latest official PMD update and actual farm conditions; the stale or unavailable forecast is not used.",
  "water.check.confirm_stage":
    "Confirm stage and irrigation history locally; no timing or amount is calculated from these inputs.",
  "water.check.last_irrigation":
    "Record the approximate date of the last irrigation before making a water decision.",
  "water.check.growth_stage":
    "Confirm the wheat growth stage by looking at the plants if it is not recorded.",
  "water.check.unavailable":
    "Confirm wheat crop and select a supported Bahawalpur pilot area before reassessment.",
  "water.check.dry":
    "Confirm dryness at root depth in several places; surface dryness alone is not enough.",
  "water.check.monitor":
    "Continue checking root-zone moisture and drainage; field observation remains primary.",
  "water.check.forecast_context":
    "Forecast is context only; it does not confirm root-zone recharge.",
  "water.check.soil_texture":
    "Note the soil texture you can identify (sandy, loamy or clayey) for the record.",
} as const;

export type BackendTextKey = keyof typeof backendEn;

/** Complete Urdu dictionary for every fixed backend sentence. */
export const backendUr: Record<BackendTextKey, string> = {
  /* ------------------------------------------------ farm plan (advisor) */
  "plan.how.crop":
    "متاثر علاقے میں کئی پودوں پر یہی جانچ دوبارہ کریں اور موازنے کے لیے ایک صحت مند لگنے والے علاقے پر بھی کریں۔",
  "plan.how.water":
    "جڑ کی گہرائی تک وہی جگہیں ہاتھ سے چیک کریں اور متاثر اور غیر متاثر علاقوں کا موازنہ کریں۔",
  "plan.how.vision":
    "رپورٹ میں بتائے گئے پودے کے حصے کو دیکھیں اور اس کا موازنہ صحت مند لگنے والے پودے سے کریں۔",
  "plan.how.farm_advisor":
    "پودے کا وہ حصہ بتائیں اور کئی پودوں کا موازنہ صحت مند لگنے والے علاقے سے کریں۔",
  "plan.what_to_observe":
    "ہر جگہ آپ کو واقعی کیا نظر آ رہا ہے، کیا یہ صحت مند لگنے والے پودوں پر بھی ایسا ہی ہے، اور کیا یہ ایک جانچ سے دوسری میں بدلتا ہے۔",
  "plan.why.crop":
    "کسان کی بتائی اور/یا تصویر میں نظر آنے والے ثبوت؛ امکانات اب بھی تصدیق شدہ نہیں۔",
  "plan.why.water":
    "محتاط مٹی اور نکاسی کی جانچ؛ کوئی آبپاشی کا شیڈول یا حکم نہیں نکالا گیا۔",
  "plan.why.vision":
    "تصویری ثبوت صرف ظاہر علامات تک محدود ہے اور وجہ کی تصدیق نہیں کر سکتا۔",
  "plan.why.vision_low_quality":
    "تصویر کا معیار کم تھا؛ ظاہری علامات کی جانچ صرف کم اعتماد والی ہے۔",
  "plan.why.insufficient": "وجہ الگ کرنے کے لیے کافی ثبوت نہیں ہے۔",
  "plan.rationale.expert":
    "پھیلنے والی، زنگ جیسی، شدید یا غیر واضح علامات کے لیے مقامی ماہر کا جائزہ ضروری ہے؛ سیسٹم کسی تصدیق شدہ وجہ کی نشاندہی نہیں کرتا۔",
  "plan.rationale.insufficient":
    "کھیت یا علامات کی اہم معلومات غائب یا غیر یقینی ہیں؛ سیسٹم عام/غیر عام کا فیصلہ نہیں نکالتا۔",
  "plan.rationale.field_inspection":
    "دستیاب رپورٹیں چند براہ راست کھیت کی جانچوں کی حمایت کرتی ہیں؛ یہ کسی وجہ کی تصدیق یا کسی عمل کا حکم نہیں دیتیں۔",
  "plan.rationale.monitor":
    "کھیت کی مزید نگرانی جاری رکھیں اور علامات بدلیں تو جانچ اپ ڈیٹ کریں۔",
  "plan.verification_step":
    "جانچ کے بعد آپ نے کیا دیکھا وہ لکھیں؛ اگر علامات پھیلیں، غیر واضح رہیں یا شدید لگیں تو محلی زرعہ افسر سے ان کا جائزہ لیں۔",
  "plan.fallback_check":
    "بتائیں پودے کا کون سا حصہ مختلف لگ رہا ہے اور کئی پودوں کا موازنہ صحت مند لگنے والے علاقے سے کریں۔",
  "plan.how.escalation":
    "جو آپ نے درج کیا ہے وہ محلی زرعہ افسر یا مستند ماہر کو دکھائیں اور ان کی رہنمائی پر عمل کریں۔",
  "plan.escalation.fallback":
    "ان نشانوں کا عمل سے پہلے محلی زرعہ افسر یا مستند ماہر سے جائزہ لیں۔",
  "plan.check.vision_cross":
    "تصویر میں دکھائے گئے پودے اور قریب کے دوسرے پودوں کے کئی پتے دیکھیں، جن میں پتے کی دونوں طرفیں بھی شامل ہیں، اور داغ، پیلا پن، زنگ جیسے نشانے یا کیڑے دیکھیں۔",

  /* ---------------------------------------------------------- conflicts */
  "conflict.wet_soil": "کسان نے گیلی مٹی یا نکاسی کا پیش آمد بتائی ہے",
  "conflict.overlap_water_stress":
    "فصل ایجنٹ نے ایسی نشانیاں پائی ہیں جو پانی کے تناؤ سے مماثل ہو سکتی ہیں",
  "conflict.wet_soil_next":
    "متاثر اور غیر متاثر جگہوں پر جڑ والی مٹی کی نمی کا موازنہ کریں؛ گیلی مٹی دوسری وجوہات کو ختم نہیں کرتی۔",
  "conflict.dry_soil": "کسان نے مشاہدے کے وقت خشک مٹی کی اطلاع دی ہے",
  "conflict.dry_vs_rain_next":
    "مشاہدے کا وقت موسم کے ٹائم اسٹیمپ سے ملائیں اور متاثر اور غیر متاثر جگہوں پر جڑ کی گہرائی تک مٹی کی نمی دوبارہ ہاتھ سے چیک کریں۔",
  "conflict.stale_weather": "موسم کی فراہمی کا ٹائم اسٹیمپ پرانا یا غائب ہے",
  "conflict.stale_weather_next":
    "کھیت کے فیصلے کے لیے یہ موسمی نتیجہ استعمال نہ کریں؛ براہ راست کھیت کی جانچیں جاری رکھیں۔",
  "conflict.crop_vision_next":
    "تصویر میں نظر آنے والی نشانیوں کا موازنہ کھیت میں آپ کی بتائی بات سے کئی پودوں پر کریں، اور اگر مطابقت نہ رکھے تو محلی زرعہ افسر سے جائزہ لیں۔",

  /* ------------------------------------------------------------- vision */
  "vision.summary.model_unavailable":
    "ذاتی وژن سروس دستیاب نہیں تھی یا ناکارہ جواب واپس آیا؛ کوئی ماڈل نتیجہ قبول نہیں ہوا۔",
  "vision.summary.no_model":
    "تصویر کا معیار درست تھا، لیکن کوئی ذاتی وژن ماڈل مقرر نہیں؛ کوئی مثال یا نمائشی نتیجہ نہیں دکھایا گیا۔",
  "vision.summary.scope_gate":
    "وژن کا نتیجہ گندم کی موزوں تصویر قائم نہیں کر سکا؛ کوئی ظاہر علامت قبول نہیں ہوئی۔",
  "vision.summary.unsafe_text":
    "ماڈل کا جواب حفاظتی گیٹ پر نہیں گزرا؛ کوئی بصری تفسیر قبول نہیں ہوئی۔",
  "vision.summary.soft_warning":
    "تصویر کا معیار محدود ہے۔ یہ کم اعتماد والی ظاہری علامات کی اسکریننگ ہے؛ ممکن ہو تو واضح قریب کی تصویر دوبارہ لیں۔",
  "vision.summary.complete":
    "تصویریں صرف ظاہر علامات بتا سکتی ہیں، ان کی وجہ کی تصدیق نہیں کر سکتیں۔",
  "vision.summary.no_photo":
    "کوئی تصویر فراہم نہیں کی گئی اس لیے وژن کا جائزہ نہیں ہوا۔",
  "vision.summary.blocked":
    "اپ لوڈ کی گئی کوئی تصویر کوالٹی چیک پاس نہیں ہوئی؛ کوئی بصری تفسیر نہیں ہوئی۔",
  "vision.obs.model_output_missing":
    "تصویر کوالٹی چیک پاس ہو گئے؛ ماڈل کا جواب دستیاب نہیں تھا۔",
  "vision.obs.gate_passed":
    "کم از کم ایک تصویر دیے گئے کوالٹی گیٹ پاس ہو گئی۔",
  "vision.obs.no_finding": "ماڈل نے کوئی موزوں ظاہر نتیجہ واپس نہیں کیا۔",
  "vision.check.continue_farmer":
    "کسان کی درج کردہ علامات استعمال کرتے رہیں یا بعد میں ذاتی ماڈل دوبارہ آزمائیں۔",
  "vision.check.connect_service":
    "منظور شدہ ذاتی وژن سروس جوڑیں یا کسان کی درج کردہ علامات کے ساتھ جاری رکھیں۔",
  "vision.check.retake_daylight":
    "دن کی روشنی میں متاثر پتے کو مرکز میں رکھ کر واضح قریب کی تصویر دوبارہ لیں۔",
  "vision.check.retake_or_farmer":
    "دن کی روشنی میں متاثر حصے کو مرکز میں رکھ کر قریب کی تصویر دوبارہ لیں، یا کسان کی درج کردہ مشاہدات کے ساتھ جاری رکھیں۔",
  "vision.check.compare_plants":
    "کئی پودوں پر ظاہر نمونے کا موازنہ کریں اور متاثر پتوں کی دونوں طرفیں دیکھیں۔",
  "vision.reason.no_evidence": "کوئی تصویری ثبوت نہیں۔",
  "vision.reason.quality_failed":
    "اپ لوڈ کی گئی تصویریں دیے گئے کوالٹی گیٹ پر ناکام ہوئیں۔",
  "vision.reason.gate_identifies":
    "کوالٹی چیک علامات کی نشاندہی نہیں کرتے؛ استدلال دستیاب نہیں ہے۔",
  "vision.reason.soft_low_confidence":
    "کم معیار کی تصویر: صرف کم اعتماد والی اسکریننگ؛ ثبوت بینڈ اور اعتماد کم پر محدود ہیں اور کوئی وجہ قائم نہیں ہوئی۔",
  "vision.reason.uncalibrated":
    "غیر موزوں ذاتی ماڈل کا جواب؛ ثبوت بینڈ تصویری ثبوت کے معیار کی وضاحت کرتا ہے، بیماری کی امکانیت کی نہیں۔ اعتماد زیادہ سے زیادہ درمیانہ ہے۔",
  "vision.reason.scope_gate":
    "ذاتی ماڈل کو crop_detected='wheat' لوٹانا ہوگا؛ غیر موجود یا غیر موزوں جواب پر انہدار ہوتا ہے۔",
  "vision.reason.unsafe_text":
    "ماڈل کے جواب میں غیر موزوں تشخیصی یا عمل کا لفظ تھا اس لیے مسترد کر دیا گیا۔",

  /* ------------------------------ vision: photo screening report strings */
  "vision.report.retake":
    "دن کی روشنی میں ایک متاثر پتے کی واضح قریب کی تصویر لیں، جس میں پتہ زیادہ تر فریم بھرے۔",
  "vision.report.visible.leaf_even": "پتے کی سطح کا رنگ عموماً یکساں لگتا ہے۔",
  "vision.report.visible.no_rust":
    "اس تصویر میں زنگ جیسے اُٹھے ہوئے نشانوں کی واضح علامت نظر نہیں آتی۔",
  "vision.report.visible.no_spots":
    "اس تصویر میں بڑے الگ دھبے واضح طور پر نظر نہیں آتے۔",
  "vision.report.interp.healthy":
    "اس تصویر میں کوئی واضح ظاہر خطرے کی نشانی نظر نہیں آتی۔ اکیلی تصویر کھیت کے دوسرے حصوں کے مسائل کو ختم نہیں کر سکتی۔",
  "vision.report.checks.both_sides":
    "اس علاقے میں کئی پتوں کی دونوں طرفیں دیکھیں اور کوئی نشانہ یا دھبہ ہے یا نہیں دیکھیں۔",
  "vision.report.checks.compare_plants":
    "اس پودے کا موازنہ اسی کھیت کے چند قریبی پودوں سے کریں۔",
  "vision.report.visible.rust_marks":
    "پتے کی سطح پر بکھرے ہوئے نارنجی بھورے گول نشانے نظر آ رہے ہیں۔",
  "vision.report.not_visible.cause": "ان نشانوں کی وجہ تصویر میں نہیں دیکھی جا سکتی۔",
  "vision.report.interp.rust":
    "زنگ جیسی ظاہری علامات موجود ہو سکتی ہیں۔ صرف تصویر سے وجہ کی تصدیق نہیں ہوتی۔",
  "vision.report.checks.rust_1":
    "5–10 متاثر پتوں کی دونوں طرفیں دیکھیں اور اُٹھے ہوئے نارنجی، پیلے یا بھورے نشانے ہیں یا نہیں دیکھیں۔",
  "vision.report.checks.rust_2":
    "متاثر پودوں کا موازنہ قریب کے صحت مند لگنے والے پودوں سے کریں۔",
  "vision.report.checks.rust_3": "چیک کریں کہ نئے پتے متاثر ہو رہے ہیں یا نہیں۔",
  "vision.report.expert.spread": "نشانے تیزی سے پھیلتے ہیں",
  "vision.report.expert.new_leaves": "نئے پتے متاثر ہو رہے ہیں",
  "vision.report.expert.larger_area": "کھیت کا بڑا حصہ متاثر ہے",
  "vision.report.interp.unclear":
    "تصویر کا معیار کافی تھا، لیکن ظاہری نشانہ اس اسکریننگ ماڈل سے درست نہیں ہو سکا۔",
  "vision.report.interp.unclassified":
    "تصویر کا معیار کافی تھا، لیکن تصویر پر جو ظاہری نشانہ سامنے آیا وہ اس اسکریننگ کی صحت مند یا زنگ جیسی نشانیوں میں سے نہیں ہے۔",
  "vision.report.visible.leaf_seen": "تصویر میں پودے کا پتہ نظر آ رہا ہے۔",
  "vision.report.not_visible.unknown_sign":
    "اس اسکریننگ سے یہ نہیں بتایا جا سکا کہ کون سی ظاہری نشانی موجود ہے۔",
  "vision.report.interp.limited":
    "اس تصویر پر ابتدائی ظاہری علامات کی اسکریننگ پھر بھی کی گئی۔ چونکہ تصویر کا معیار محدود ہے، یہ تصویر ظاہری علامات کو ختم نہیں کر سکتی۔",
  "vision.report.not_visible.elsewhere":
    "اکیلی تصویر کھیت کے دوسرے حصوں کی حالت نہیں دکھا سکتی۔",
  "vision.report.interp.blocked":
    "کوئی اپ لوڈ کی گئی تصویر فوٹو کوالٹی چیک پاس نہیں ہوئی، اس لیے کوئی ظاہری علامات کی اسکریننگ نہیں ہوئی۔",
  "vision.report.not_visible.nothing":
    "کوئی تصویر جانچنے کے لیے دستیاب نہیں تھی، اس لیے کچھ بھی جانچا نہیں گیا۔",
  "vision.quality.too_large":
    "فوٹو فائل بہت بڑی ہے۔ براہِ کرم 10 MB سے کم کی تصویر بھیجیں۔",
  "vision.quality.bad_file":
    "یہ فائل فوٹو کے طور پر کھولی نہیں جا سکی۔ براہِ کرم JPG یا PNG بھیجیں۔",
  "vision.quality.low_resolution":
    "تصویر بہت چھوٹی ہے۔ براہِ کرم عام کیمرے سے مکمل معیار پر لیں۔",
  "vision.quality.blurry":
    "تصویر دھندلی ہے۔ فون مضبوط پکڑیں اور فوکس کے لیے پتے پر ٹیپ کریں۔",
  "vision.quality.too_dark": "تصویر بہت اندھیری ہے۔ براہِ کرم دن کی روشنی میں لیں۔",
  "vision.quality.too_bright":
    "تصویر بہت روشن ہے یا اس میں چمک ہے۔ کیمرے پر براہِ کرم براہِ راست دھوپ نہ پڑنے دیں۔",
  "vision.quality.no_plant":
    "کوئی فصل نظر نہیں آ رہی۔ قریب آئیں تاکہ پتے تصویر کا زیادہ تر حصہ بھریں۔",
  "vision.quality.image_unreadable":
    "یہ تصویر پڑھی نہیں جا سکی۔ براہِ کرم JPG یا PNG تصویر بھیجیں۔",
  "vision.quality.no_image_supplied":
    "کوئی تصویر فراہم نہیں کی گئی، اس لیے کچھ بھی جانچا نہیں جا سکا۔",

  /* --------------- vision: plant part / screening scope (leaf vs ear) */
  "vision.scope.leaf_fill":
    "یہ قریبی تصویر ہے جس میں پتے بھرے ہوئے ہیں، اس لیے پتے کی علامات کی اسکریننگ لاگو ہوتی ہے۔",
  "vision.scope.ear_straw":
    "تصویر میں سنہری پتلی رنگ کے خوشے کی بافت بھری ہوئی ہے، اس لیے یہ تصویر پتا نہیں بلکہ گندم کا خوشہ ہے۔",
  "vision.scope.ear_shape":
    "تصویر میں قریبی پتے کے بجائے پس منظر کے مقابلے کھڑی گندم کی پودی نظر آ رہی ہے، اس لیے یہ پتا نہیں بلکہ خوشہ ہے۔",
  "vision.scope.ear_ripe":
    "یہ صاف قریبی تصویر ہے جس میں پتوں کے بجائے پکی ہوئی گندم کے خوشوں کا سنہری رنگ بھرا ہوا ہے، اس لیے یہ پتا نہیں بلکہ گندم کا خوشہ ہے۔",
  "vision.scope.field_sky":
    "تصویر میں افق اور کھلا آسمان نظر آ رہا ہے، اس لیے یہ قریبی پتے کے بجائے کھیت کا وسیع نظارہ ہے۔",
  "vision.scope.field_patches":
    "فصل ایک قریبی تصویر کے بجائے بکھرے ہوئے چھوٹے حصوں میں نظر آ رہی ہے، اس لیے یہ کھیت کا وسیع نظارہ ہے۔",
  "vision.scope.not_leaf":
    "تصویر میں پتے نہیں بھرے ہوئے، اس لیے پتے کی علامات کی اسکریننگ لاگو نہیں کی گئی۔",
  "vision.scope.other_plant":
    "تصویر میں پودے کا حصہ نظر آ رہا ہے، لیکن یہ گندم کے پتے کی قریبی تصویر نہیں ہے۔",
  "vision.scope.no_wheat":
    "اس تصویر سے گندم پہچانا نہیں جا سکا، اس لیے گندم کے پتے کی اسکریننگ لاگو نہیں کی گئی۔",
  "vision.scope.subject_unclear":
    "تصویر میں پودے کا حصہ پہچاننے کے لیے تفصیلات کافی نہیں ہیں۔",
  "vision.scope.mixed":
    "تصویریں ایک ہی چیز نہیں دکھاتیں؛ ایک متاثر پتے کی صاف قریبی تصویر درکار ہے۔",
  "vision.scope.quality_failed":
    "کسی تصویر نے معیار کی جانچ مکمل نہیں کی، اس لیے تصویر کا حصہ پہچانا نہیں جا سکا۔",
  "vision.scope.no_photo":
    "کوئی تصویر فراہم نہیں کی گئی، اس لیے تصویر کا حصہ پہچانا نہیں جا سکا۔",
  "vision.report.not_visible.scope": "اس تصویر سے پتے کی علامات کا جائزہ نہیں لیا جا سکتا۔",
  "vision.report.checks.scope":
    "اس پودے اور قریب کے چند پودوں کے پتے کسی بھی نشان یا داغ کے لیے دیکھیں۔",
  "vision.report.retake.scope":
    "دن کی روشنی میں ایک متاثر پتے کی صاف قریبی تصویر لیں، جس میں پتا زیادہ تر فریم بھرے۔",
  "vision.report.visible.ear": "اس تصویر میں پکی ہوئی گندم کا خوشہ نظر آ رہا ہے۔",
  "vision.report.not_visible.ear":
    "چونکہ اس تصویر میں قریبی پتا نہیں ہے، اس لیے پتے کی علامات کا جائزہ نہیں لیا جا سکتا۔",
  "vision.report.interp.ear":
    "یہ پکے گندم کے خوشے کی صاف تصویر ہے، پتے کی نہیں۔",
  "vision.report.visible.field": "اس تصویر میں پورے کھیت میں فصل کا نظارہ نظر آ رہا ہے۔",
  "vision.report.interp.field":
    "یہ تصویر صاف ہے، لیکن یہ فصل کو دور سے دکھاتی ہے۔ پورے کھیت یا دور کی تصویر سے پتے کی علامات کا جائزہ نہیں لیا جا سکتا۔",
  "vision.report.visible.other_plant":
    "تصویر میں پودے کا حصہ نظر آ رہا ہے، لیکن یہ گندم کے پتے کی قریبی تصویر نہیں ہے۔",
  "vision.report.interp.other_plant":
    "یہ تصویر گندم کے پتے کی قریبی تصویر نہیں دکھاتی، اس لیے پتے کی علامات کی اسکریننگ لاگو نہیں کی گئی۔",
  "vision.report.visible.subject_unclear":
    "اس تصویر میں نظر آنے والا حصہ واضح طور پر پہچانا نہیں جا سکا۔",
  "vision.report.interp.subject_unclear":
    "تصویر میں نظر آنے والا حصہ پہچانا نہیں جا سکا، اس لیے پتے کی علامات کی اسکریننگ لاگو نہیں کی گئی۔",
  "vision.report.interp.scope_limited":
    "تصویر کا معیار محدود ہے اور یہ اسکریننگ قریبی پتے کی علامات کے لیے بنی ہے، اس لیے اس تصویر سے پتے کی علامات کا جائزہ نہیں لیا گیا۔",
  "vision.report.obs.ear":
    "تصویر میں گندم کا خوشہ نظر آ رہا ہے؛ پتے کی علامات کی اسکریننگ لاگو نہیں کی گئی۔",
  "vision.report.obs.field":
    "تصویر میں فصل دور سے نظر آ رہی ہے؛ ایک متاثر پتے کی قریبی تصویر درکار ہے۔",
  "vision.report.obs.other_plant":
    "تصویر میں پودے کا حصہ نظر آ رہا ہے، لیکن یہ گندم کے پتے کی قریبی تصویر نہیں ہے۔",

  /* ----------------------------------------------------- weather / crop */
  "weather.summary.context":
    "موسمی قدریں فراہم کنندہ کی پیشگویی گرڈ کی سیاق و سباق ہیں، کھیت کی پیمائش نہیں۔",
  "weather.summary.unavailable":
    "موسمی ڈیٹا دستیاب نہیں؛ دوسرے ایجنٹ بغیر موسمی ااعدالے کے جاری رہتے ہیں۔",
  "weather.obs.no_values":
    "فراہمی کے جواب میں کوئی ایسا موجودہ عدد نہیں تھا جو تصدیق پاس کرے۔",
  "weather.obs.no_rain_24h":
    "اگلے 24 گھنٹے میں کوئی نمایاں بارش کی پیشگویی نہیں ہے؛ کسی بھی پانی کے فیصلے سے پہلے کھیت کی نمی کی تصدیق کریں۔",
  "weather.obs.rain_24h":
    "بارش کی پیشگویی ہے، لیکن یہ جڑ کی نمی بھرنے کی تصدیق نہیں کرتی۔",
  "weather.obs.grid_context":
    "پیشگویی کی قدریں گرڈ کا سیاق ہیں، اس کھیت کی پیمائش نہیں۔",
  "weather.obs.no_24h_series":
    "پرووائیڈر نے اگلے 24 گھنٹے کی سیریز واپس نہیں کی، اس لیے بارش کا کوئی بیان نہیں کیا گیا۔",
  "crop.summary.unsupported":
    "فصل ایجنٹ صرف گندم کے لیے ہے؛ اس فصل کا کوئی جائزہ نہیں ہوا۔",
  "crop.check.unsupported":
    "گندم منتخب کریں یا اس فصل کے بارے میں مقامی زرعہ ماہر سے پوچھیں۔",
  "crop.summary.insufficient":
    "ممکن اسباب الگ کرنے کے لیے علامات کا کافی ثبوت نہیں ہے۔",
  "crop.summary.screening":
    "نیچے دیے گئے نتائج صرف اسکریننگ کے امکانات ہیں؛ ملتی جلتی ظاہر تبدیلیوں کی مختلف وجوہات ہو سکتی ہیں۔",

  /* ------------------------------------------------------------ market */
  "market.check.enter_quote":
    "حالیہ مارکیٹ قیمت درج کریں یا موجودہ ریٹ کے لیے مقامی مارکیٹ کمیٹی سے پوچھیں۔",
  "market.check.ask_rate":
    "اس نمبر پر انحصار سے پہلے آج کے ریٹ کے لیے مقامی مارکیٹ کمیٹی یا آڑھتی سے پوچھیں۔",
  "market.check.confirm_unit":
    "قیمت بتانے والے شخص سے اکائی اور گریڈ کی تصدیق کریں۔",
  "market.check.real_quote":
    "ڈیمو کے علاوہ ہر استعمال کے لیے حقیقی مشاہدہ شدہ قیمت استعمال کریں؛ یہ نمائشی ہے۔",
  "market.check.confirm_all":
    "انحصار سے پہلے ماخذ سے قیمت، اکائی، بازار اور مشاہدے کی تاریخ کی تصدیق کریں۔",
  "market.obs.farmer_reported":
    "کسان نے یہ قیمت بتائی ہے؛ KisanOS نے اسے حاصل یا تصدیق نہیں کیا۔",
  "market.reason.no_quote":
    "کوئی مارکیٹ قیمت حاصل یا فراہم نہیں ہوئی؛ کوئی قیمت نہیں نکالی گئی۔",

  /* ------------------------------------- official AMIS (Punjab) results */
  "market.summary.amis_missing_bahawalpur":
    "قیمت دستیاب نہیں: آج AMIS کی جانب سے بہاولپور کی تصدیق شدہ گندم کی قیمت واپس نہیں کی گئی۔",
  "market.summary.amis_unreachable":
    "قیمت دستیاب نہیں: سرکاری AMIS قیمت کا صفحہ دستیاب نہیں ہوا، اس لیے آج کوئی تصدیق شدہ قیمت موجود نہیں ہے۔",
  "market.summary.amis_unusable":
    "قیمت دستیاب نہیں: AMIS نے آج قابل استعمال گندم کی قیمت فراہم نہیں کی۔",
  "market.obs.amis_retrieved":
    "پنجاب AMIS سے حاصل کیا گیا؛ KisanOS نے کوئی قیمت نہیں بدلی، نہ اندازہ لگایا اور نہ کوئی قیمت بنائی۔",
  "market.obs.amis_stale":
    "AMIS کی قیمت کی تاریخ ۲۴ گھنٹے سے پرانی ہے، اس لیے اسے موجودہ قیمت نہیں کہا جا رہا۔",
  "market.obs.amis_no_date": "AMIS نے اس قیمت کی تاریخ فراہم نہیں کی۔",
  "market.obs.amis_only_farmer":
    "آج پنجاب AMIS سے قابل استعمال قیمت نہیں ملی، اس لیے صرف کسان کی درج کردہ قیمت دکھائی جا رہی ہے۔",
  "market.reason.amis_fresh":
    "یہ پنجاب AMIS کی جانب سے بتائی ہوئی قیمت ہے؛ تازگی AMIS کی قیمت کی تاریخ پر مبنی ہے، اور KisanOS نے کوئی قیمت نہیں بدلی یا بنائی۔",
  "market.reason.amis_stale":
    "پنجاب AMIS کی قیمت کی تاریخ ۲۴ گھنٹے سے پرانی ہے؛ یہ قیمت پرانی ہے اور موجودہ قیمت کے طور پر پیش نہیں کی جا رہی۔",
  "market.reason.amis_no_date":
    "پنجاب AMIS نے قیمت کی تاریخ فراہم نہیں کی؛ یہ قیمت ذریعے کی طرف سے بتائی ہوئی ہے اور اس کی تاریخ دستیاب نہیں، آج کی قیمت نہیں۔",
  "market.check.amis_confirm":
    "دوسرے ریٹ سے موازنہ کرنے سے پہلے منڈی سے اکائی اور قسم کی تصدیق کریں۔",

  /* ------------------------------------- crop: farmer/photo observations */
  "crop.obs.yellowing": "کسان نے پیلہ پن دیکھا ہے",
  "crop.obs.spots": "کسان نے داغ یا دھبے دیکھے ہیں",
  "crop.obs.rust_like": "کسان نے زنگ جیسے نشانے دیکھے ہیں",
  "crop.obs.wilting": "کسان نے پودوں کا مرجھانا یا پتوں کا لپیٹنا دیکھا ہے",
  "crop.obs.drying": "کسان نے وقت سے پہلے خشک ہونا دیکھا ہے",
  "crop.obs.insects": "کسان نے ظاہر کیرے دیکھے ہیں",
  "crop.obs.mildew_like": "کسان نے سفید پرالی جیسا منظر دیکھا ہے",
  "crop.obs.lodging": "کسان نے پودوں کا جھکنا یا گرنا دیکھا ہے",
  "crop.obs.unknown": "کسان کو یقین نہیں کہ یہ کون سی علامت ہے",

  /* --------------------------------------- crop: farmer-answerable checks */
  "crop.check.older_younger":
    "پرانے اور نئے پتوں کا موازنہ کریں اور نوٹ کریں کہ تبدیلی پرانے پتوں سے شروع ہوتی ہے یا نئے پتوں سے۔",
  "crop.check.uniform_patchy":
    "چیک کریں کہ یہ نمونہ پورے کھیت میں یکساں ہے یا ٹوٹا ہوا۔",
  "crop.check.both_sides":
    "کئی متاثر پتوں کی دونوں طرفیں دیکھیں: داغوں کی شکل اور رنگ، وہ پتے کہاں بیٹھے ہیں، اور پتے کی دونوں سطحیں متاثر ہیں یا نہیں۔",
  "crop.check.rolling_wilting":
    "نوٹ کریں کہ پتے لپٹ رہے ہیں یا پودے مرجھا رہے ہیں، اور کیا وہ رات کو واپس ٹھیک ہوتے ہیں۔",
  "crop.check.insects":
    "پتوں کے نیچے اور پودے کی جڑ کے آس پاس دیکھیں، اور کئی پودوں پر کیرے نظر آ رہے ہیں یا نہیں درج کریں۔",
  "crop.check.irrigation_rain":
    "پوچھیں کہ کھیت میں حال ہی میں آبپاشی یا بارش ہوئی تھی اور اس کے بعد علامات بدلیں یا نہیں۔",
  "crop.check.spreading":
    "متاثر علاقے کا کنارہ نشان زد کریں اور درج کریں کہ علامات کنارے سے اندر پھیل رہی ہیں یا کھیت میں الگ الگ جگہوں پر ہیں۔",
  "crop.check.inspect_plants":
    "کھیت میں کئی پودے دیکھیں اور متاثر حصوں کا موازنہ صحت مند لگنے والے حصوں سے کریں۔",
  "crop.check.describe_pattern":
    "بتائیں پودے کا کون سا حصہ مختلف لگ رہا ہے اور نمونہ یکساں ہے یا ٹوٹا ہوا۔",
  "crop.check.compare_healthy":
    "کئی متاثر پودوں کا موازنہ صحت مند لگنے والے علاقے سے کریں۔",
  "crop.check.root_zone":
    "کسی وجہ کا فیصلہ کرنے سے پہلے جڑ کے علاقے کی مٹی کی نمی، نکاسی اور جڑیں دیکھیں۔",
  "crop.check.compare_dry":
    "کئی جگہوں پر خشک پودوں کا موازنہ صحت مند لگنے والے پودوں سے کریں۔",
  "crop.check.dry_origin":
    "درج کریں کہ خشک ہونا پتے کی نکوں سے شروع ہوتا ہے، کناروں سے، یا پورے پتے سے۔",
  "crop.check.patches":
    "کئی جگہوں پر متاثر اور غیر متاثر علاقوں کا موازنہ کریں۔",
  "crop.check.rust_1":
    "کئی متاثر پتوں کی دونوں طرفیں دیکھیں اور درج کریں کہ نمایاں نارنجی، پیلے یا بھورے نشانے اُٹھے ہوئے ہیں یا نہیں۔",
  "crop.check.rust_2":
    "متاثر پودوں کا موازنہ قریب کے صحت مند لگنے والے پودوں سے کریں اور نوٹ کریں کہ نشانے بکھرے ہیں یا قطاروں میں ہیں۔",
  "crop.check.rust_3": "چیک کریں کہ نئے پتے متاثر ہو رہے ہیں یا نہیں۔",
  "crop.check.photo_discrepancy":
    "اپ لوڈ کی گئی تصویر میں واضح علامات نظر نہیں آئیں، جبکہ کسان نے علامات بتائیں۔ متاثر پودوں کی کئی جگہوں پر جانچ کریں؛ تصویر کھیت کے کسی مسئلے کو منتفی نہیں کرتی۔",
  "crop.check.photo_limit":
    "اپ لوڈ کی گئی تصویر میں پڑھنے لائق تفصیلات نہیں تھیں، اس لیے اس سے کوئی واضح نشانہ نہیں پڑھا گیا؛ یہ صرف تصویر کے شواہدات تک محدود ہے اور کھیت کے بارے میں کچھ نہیں بتاتا۔",
  "crop.photo.ear_scope":
    "تصویر میں گندم کا خوشہ نظر آ رہا ہے۔ اس تصویر میں اسکریننگ کے لیے پتے کی علامات نہیں ہیں۔",
  "crop.check.referral":
    "عمل سے پہلے پھیلنے والی، زنگ جیسی، شدید یا غیر واضح علامات کا محلی زرعہ افسر یا مستند ماہر سے جائزہ لیں۔",

  /* ------------------------------------------ crop: screening possibilities */
  "crop.poss.water_stress": "پانی کی ممکنہ کمی",
  "crop.poss.nutrient_stress": "غذائیت کی ممکنہ کمی",
  "crop.poss.premature_drying": "وقت سے پہلے خشک ہونا؛ متعدد وجوہات ممکن ہیں",
  "crop.poss.rust_symptoms": "زنگ جیسے نشانے",
  "crop.poss.leaf_spots": "پتے پر داغ یا کسی بیماری کی ممکنہ علامت",
  "crop.poss.insect_damage": "کیڑوں کا ممکنہ نقصان",
  "crop.poss.rust":
    "زنگ جیسے پتے کے نشانوں کی کھیت میں جانچ درکار ہے؛ وجہ تصدیق شدہ نہیں۔",
  "crop.poss.no_distinction": "دستیاب شواہدات کسی ایک وجہ کو الگ نہیں کرتے",
  "crop.poss.cannot_assess": "دی گئی معلومات سے وجہ کا اندازہ نہیں لگایا جا سکتا",

  /* --------------------------------------------------- crop: escalation signs */
  "crop.escalation.rust":
    "اگر نشانے تیزی سے پھیلیں، نئے پتوں پر آئیں یا کھیت کے بڑے حصے کو متاثر کریں تو مقامی ماہر سے جائزہ لیں۔",
  "crop.escalation.spreading":
    "اگر متاثر علاقہ تیزی سے پھیلتا رہے یا نئے پودے متاثر ہوں تو مقامی ماہر سے جائزہ لیں۔",
  "crop.escalation.conflict":
    "ایسے نشانات جو ایک دوسرے سے مطابقت نہیں رکھتے، ان کا عمل سے پہلے محلی زرعہ افسر سے جائزہ لیں۔",
  "crop.escalation.stage":
    "گندم کے پھول اور دانہ بنتے مرحلوں پر دی گئی علامات کا محلی زرعہ افسر سے جائزہ لیں۔",
  "crop.escalation.chemical":
    "کسی بھی پروڈکٹ یا انپٹ کے سوال کا جواب عمل سے پہلے محلی زرعہ افسر سے لیں۔",
  "crop.escalation.unclear":
    "غیر واضح یا شدید لگنے والے نشانات کا عمل سے پہلے محلی زرعہ افسر سے جائزہ لیں۔",

  /* ------------------------------------------------ water: field checks */
  "water.check.soil_moisture":
    "جڑ کے علاقے کی مٹی کو 3–5 نمایاں جگہوں پر ہاتھ سے دیکھیں؛ متاثر اور صحت مند لگنے والے علاقوں کا موازنہ کریں۔",
  "water.check.drainage_paths":
    "کھڑے پانی، بند نکاسی کے نکاس، اور آبپاشی یا بارش کے بعد مٹی میں نمی باقی ہے یا نہیں، دیکھیں۔",
  "water.check.after_rain":
    "بارش واقعی ہونے کے بعد جڑ کی مٹی کی نمی دوبارہ چیک کریں؛ پیشگوئی کو پانی بھرنے کا ثبوت نہ سمجھیں۔",
  "water.check.pmd_update":
    "PMD کا تازہ ترین سرکاری اپڈیٹ اور کھیت کی حقیقی حالت دیکھیں؛ پرانا یا دستیاب نہ ہونے والے پیشگویی کا ڈیٹا استعمال نہیں ہوتا۔",
  "water.check.confirm_stage":
    "مقامی طور پر کھیت کا مرحلہ اور آبپاشی کی تاریخ کی تصدیق کریں؛ ان سے کوئی وقت یا مقدار نہیں نکالی جاتی۔",
  "water.check.last_irrigation":
    "پانی کے بارے میں فیصلے سے پہلے آخری آبپاشی کی تقریبی تاریخ درج کریں۔",
  "water.check.growth_stage":
    "اگر گندم کا نمو کا مرحلہ درج نہیں ہے تو پودوں کو دیکھ کر مرحلہ درست کریں۔",
  "water.check.unavailable":
    "دوبارہ جانچ سے پہلے گندم کی فصل کی تصدیق کریں اور بہاولپور پائلٹ کا کوئی موزوں علاقہ منتخب کریں۔",
  "water.check.dry":
    "کئی جگہوں پر جڑ کی گہرائی تک خشکی کی تصدیق کریں؛ صرف سطحی خشکی کافی نہیں۔",
  "water.check.monitor":
    "جڑ کے علاقے کی نمی اور نکاسی جانچتے رہیں؛ کھیت کی نگرانی ہی بنیاد ہے۔",
  "water.check.forecast_context":
    "پیشگویی صرف سیاق ہے؛ یہ جڑ کی مٹی میں پانی بھرنے کی تصدیق نہیں کرتی۔",
  "water.check.soil_texture":
    "ریکارڈ کے لیے وہ مٹی کی قسم درج کریں جو آپ پہچان سکتے ہیں (ریتلی، دو رتی یا چکنی)۔",
};

/* --------------------------------------------------------------- prefixes */

/**
 * English labels that appear as `"<label>: <dynamic detail>"` (Vision's safe
 * visible-sign vocabulary) or on their own as a whole observation.
 * Mapped to the Urdu label; the dynamic tail stays English.
 */
export const backendPrefixEn = {
  "vision.label.healthy_looking": "No clear visible symptoms",
  "vision.label.yellowing": "Visible yellowing",
  "vision.label.rust_like_pustules": "Rust-like marks visible; cause not confirmed",
  "vision.label.spots_or_blotches": "Visible spots or blotches",
  "vision.label.visible_insects": "Visible insects",
  "vision.label.drying": "Visible drying",
  "vision.label.unclear": "Image details unclear",
  "vision.obs.quality_issue": "Photo quality issue",
  "conflict.crop_evidence": "Crop Agent evidence",
  "conflict.vision_signs": "Vision Agent visible signs",
  "market.summary.price_unavailable": "Price unavailable",
  "market.summary.amis_price": "AMIS wheat price",
  "market.obs.source_date": "Source date",
  "market.obs.retrieved_at": "Retrieved at",
  "market.obs.source_url": "Source URL",
  "crop.obs.photo_visible": "Photo visible",
} as const;

export type BackendPrefixKey = keyof typeof backendPrefixEn;

/** Complete Urdu dictionary for every known English label prefix. */
export const backendPrefixUr: Record<BackendPrefixKey, string> = {
  "vision.label.healthy_looking": "تصویر میں واضح علامات نظر نہیں آئیں",
  "vision.label.yellowing": "ظاہر پیلہ پن نظر آ رہا ہے",
  "vision.label.rust_like_pustules": "زنگ جیسے نشانے ظاہر ہیں؛ وجہ تصدیق شدہ نہیں",
  "vision.label.spots_or_blotches": "ظاہر داغ یا دھبے نظر آ رہے ہیں",
  "vision.label.visible_insects": "ظاہر کیرے نظر آ رہے ہیں",
  "vision.label.drying": "خشک ہونا ظاہر ہے",
  "vision.label.unclear": "تصویر کی تفصیلات واضح نہیں",
  "vision.obs.quality_issue": "تصویر کوالٹی کا مسئلہ",
  "conflict.crop_evidence": "فصل ایجنٹ کا ثبوت",
  "conflict.vision_signs": "وژن ایجنٹ کی ظاہر نشانیاں",
  "market.summary.price_unavailable": "قیمت دستیاب نہیں",
  "market.summary.amis_price": "AMIS گندم کی قیمت",
  "market.obs.source_date": "قیمت کی تاریخ",
  "market.obs.retrieved_at": "وصول کیا گیا",
  "market.obs.source_url": "ذریعے کا لنک",
  "crop.obs.photo_visible": "تصویر میں نظر آیا",
};

const UR_BY_ENGLISH: ReadonlyMap<string, string> = new Map(
  (Object.keys(backendEn) as BackendTextKey[]).map((key) => [backendEn[key], backendUr[key]]),
);

const UR_BY_PREFIX: ReadonlyArray<{ en: string; ur: string }> = (
  Object.keys(backendPrefixEn) as BackendPrefixKey[]
).map((key) => ({ en: backendPrefixEn[key], ur: backendPrefixUr[key] }));

export interface BackendTextMatch {
  /** Urdu rendering of the known part. */
  urdu: string;
  /** Dynamic English tail after `"<label>: "` — null when fully mapped. */
  rest: string | null;
}

/**
 * Look up one backend string. Returns `null` when no reliable Urdu exists,
 * so callers can show the English original under its visible label.
 */
export function matchBackendText(text: string): BackendTextMatch | null {
  const source = text.trim();
  if (!source) return null;

  const exact = UR_BY_ENGLISH.get(source);
  if (exact) return { urdu: exact, rest: null };

  for (const { en, ur } of UR_BY_PREFIX) {
    if (source === en) return { urdu: ur, rest: null };
    if (source.startsWith(`${en}:`)) {
      const rest = source.slice(en.length + 1).trim();
      return { urdu: ur, rest: rest || null };
    }
  }
  return null;
}

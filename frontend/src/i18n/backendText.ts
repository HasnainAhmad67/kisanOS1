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

  /* ----------------------------------------------------- weather / crop */
  "weather.summary.context":
    "Weather values are provider-reported forecast-grid context, not field measurements.",
  "weather.summary.unavailable":
    "Weather data is unavailable; other assessment agents continue without weather-driven rules.",
  "weather.obs.no_values":
    "Provider response contained no current values that passed validation.",
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
    "Check whether the pattern is uniform across the field or patchy, and press the root-zone soil by hand in an affected spot and in a healthy-looking spot.",
  "crop.check.both_sides":
    "Inspect both sides of several affected leaves: note the colour of any spots or pustules, where they sit on the leaf, and whether healthy-looking plants nearby are unaffected.",
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
  "crop.check.referral":
    "Ask a local agriculture officer or qualified expert to review spreading, rust-like, severe, or unclear symptoms and any treatment question before any action.",

  /* ------------------------------------------------ water: field checks */
  "water.check.soil_moisture":
    "Check soil moisture by hand at root depth in several representative spots and compare affected and healthy-looking areas.",
  "water.check.drainage_paths":
    "Inspect low spots and drainage paths; ask local extension staff to review persistent standing water or uncertain conditions.",
  "water.check.after_rain":
    "After rainfall is actually observed, re-check root-zone soil moisture; do not treat the forecast as proof of recharge.",
  "water.check.pmd_update":
    "Check the latest official PMD update and actual farm conditions; the stale or unavailable forecast is not used.",
  "water.check.confirm_stage":
    "Confirm stage and irrigation history locally; no timing or amount is calculated from these inputs.",
  "water.check.unavailable":
    "Confirm wheat crop and select a supported Bahawalpur pilot area before reassessment.",
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

  /* ----------------------------------------------------- weather / crop */
  "weather.summary.context":
    "موسمی قدریں فراہم کنندہ کی پیشگویی گرڈ کی سیاق و سباق ہیں، کھیت کی پیمائش نہیں۔",
  "weather.summary.unavailable":
    "موسمی ڈیٹا دستیاب نہیں؛ دوسرے ایجنٹ بغیر موسمی ااعدالے کے جاری رہتے ہیں۔",
  "weather.obs.no_values":
    "فراہمی کے جواب میں کوئی ایسا موجودہ عدد نہیں تھا جو تصدیق پاس کرے۔",
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
    "چیک کریں کہ یہ نمونہ پورے کھیت میں یکساں ہے یا ٹوٹا ہوا، اور متاثر جگہ اور صحت مند لگنے والی جگہ پر جڑ کی مٹی ہاتھ سے دبائیں۔",
  "crop.check.both_sides":
    "کئی متاثر پتوں کی دونوں طرفیں دیکھیں: داغوں یا پھوڑوں کا رنگ، وہ پتے کہاں بیٹھے ہیں، اور قریب کے صحت مند لگنے والے پودے متاثر ہیں یا نہیں۔",
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
  "crop.check.referral":
    "عمل سے پہلے پھیلنے والی، زنگ جیسی، شدید یا غیر واضح علامات اور کسی بھی علاج کے سوال کا محلی زرعہ افسر یا مستند ماہر سے جائزہ لیں۔",

  /* ------------------------------------------------ water: field checks */
  "water.check.soil_moisture":
    "کئی نمایاں جگہوں پر جڑ کی گہرائی تک مٹی کی نمی ہاتھ سے چیک کریں اور متاثر اور صحت مند لگنے والے علاقوں کا موازنہ کریں۔",
  "water.check.drainage_paths":
    "نیچی جگہوں اور نکاسی کے راستے دیکھیں؛ مستقل پانی جمع ہونے یا غیر یقینی حالت پر مقامی تعلیمی عملے سے جائزہ لیں۔",
  "water.check.after_rain":
    "بارش واقعی ہونے کے بعد جڑ کی مٹی کی نمی دوبارہ چیک کریں؛ پیشگوئی کو پانی بھرنے کا ثبوت نہ سمجھیں۔",
  "water.check.pmd_update":
    "PMD کا تازہ ترین سرکاری اپڈیٹ اور کھیت کی حقیقی حالت دیکھیں؛ پرانا یا دستیاب نہ ہونے والے پیشگویی کا ڈیٹا استعمال نہیں ہوتا۔",
  "water.check.confirm_stage":
    "مقامی طور پر کھیت کا مرحلہ اور آبپاشی کی تاریخ کی تصدیق کریں؛ ان سے کوئی وقت یا مقدار نہیں نکالی جاتی۔",
  "water.check.unavailable":
    "دوبارہ جانچ سے پہلے گندم کی فصل کی تصدیق کریں اور بہاولپور پائلٹ کا کوئی موزوں علاقہ منتخب کریں۔",
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

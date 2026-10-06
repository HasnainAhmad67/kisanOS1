import type { DictKey } from "./en";

/** Complete Urdu (Nastaliq) dictionary — every English key implemented. */
export const ur: Record<DictKey, string> = {
  /* ------------------------------------------------------------- common */
  "common.back": "واپس",
  "common.loading": "لوڈ ہو رہا ہے…",
  "common.tryAgain": "دوبارہ کوشش کریں",
  "common.remove": "حذف کریں",
  "common.notSure": "نہیں معلوم",
  "common.known": "معلوم",

  /* ------------------------------------------------------- navigation */
  "nav.newCheck": "نیا چیک",
  "nav.myChecks": "میری چیکس",
  "nav.guidance": "رہنمائی",
  "nav.settings": "ترتیبات",
  "nav.team": "ٹیم",
  "nav.main": "مرکزی نیویگیشن",

  /* ------------------------------------------------------------- shell */
  "app.skip": "مواد پر جائیں",
  "app.langLabel": "زبان",
  "app.footer":
    "کسان OS · بہاولپور گندم پائلٹ — صرف اسکریننگ میں مدد، تصدیق شدہ تشخیص نہیں۔",

  /* ----------------------------------------------------------- welcome */
  "welcome.greeting": "خوش آمدید",
  "welcome.title": "نیا کھیت چیک",
  "welcome.tagline": "کسان کے لیے AI فیصلہ سہارا",
  "welcome.intro":
    "اپنے گندم کے کھیت میں کیا نظر آ رہا ہے ہمیں بتائیں، چند تصویریں شامل کریں، اور چند منٹ میں اگلا کیا چیک کرنا ہے اس کا مختصر منصوبہ پائیں۔",
  "welcome.howTitle": "یہ کیسے کام کرتا ہے",
  "welcome.how1": "اپنے کھیت کے بارے میں چند سوالوں کے جواب دیں۔",
  "welcome.how2": "متاثر پتوں کے قریب سے صاف تصویریں لیں۔",
  "welcome.how3":
    "پانچ ایجنٹ کارڈ (موسم، پانی، فصل، وژن، مارکیٹ) اور اپنا فارم پلان دیکھیں۔",
  "welcome.safetyTitle": "تحذیر",
  "welcome.configLoading": "ترتیب لوڈ ہو رہی ہے…",
  "welcome.configUnavailable": "ترتیب دستیاب نہیں",
  "welcome.crop": "فصل:",
  "welcome.areas": "پائلٹ علاقے:",
  "welcome.cta": "نیا چیک شروع کریں",

  /* ------------------------------------------------------ farm details */
  "farm.title": "کھیت کی تفصیلات",
  "farm.intro":
    "* سے نشان زد فیلڈز درکار ہیں۔ باقی سب میں “نہیں معلوم” رکھ سکتے ہیں۔",
  "farm.cropLegend": "فصل",
  "farm.cropHint": "پائلٹ میں صرف گندم ہے۔",
  "farm.cropConfirm": "میں تصدیق کرتا ہوں یہ کھیت گندم کا ہے",
  "farm.areaLabel": "علاقہ",
  "farm.areaPlaceholder": "اپنا پائلٹ علاقہ منتخب کریں",
  "farm.areaLoading": "علاقے لوڈ ہو رہے ہیں…",
  "farm.areaConfirmLegend": "علاقے کی تصدیق",
  "farm.areaConfirm": "میں بہاولپور کے اس پائلٹ علاقے کی تصدیق کرتا ہوں",
  "farm.growthLabel": "فصل کی نشوونما کی حالت",
  "farm.irrigationLabel": "آبپاشی کی تاریخ",
  "farm.lastIrrigation": "آخری آبپاشی",
  "farm.soilTexture": "مٹی کی قسم",
  "farm.soilMoisture": "مٹی کی نمی (ہاتھ سے)",
  "farm.drainage": "پانی کی نکاسی",
  "farm.onsetLabel": "علامات کب شروع ہوئیں؟",
  "farm.spreadingLegend": "کیا علامات پھیل رہی ہیں؟",
  "farm.symptomsLegend": "جو علامات نظر آ رہی ہیں",
  "farm.symptomsHint": "کم از کم ایک منتخب کریں۔",
  "farm.symptomsError": "کم از کم ایک علامت منتخب کریں۔",
  "farm.notesLabel": "نوٹس",
  "farm.notesHint": "1500 حروف تک۔ اختیاری۔",
  "farm.privacyLegend": "رازداری",
  "farm.privacyHint":
    "جانچ محفوظ کرنے کے لیے اجازت درکار ہے۔ جی پی ایس مقامات جمع نہیں کیے جاتے۔",
  "farm.consent":
    "میں اس جانچ اور اس کی تصویروں کو اپنے استعمال کے لیے محفوظ کرنے سے اتفاق کرتا ہوں",
  "farm.geminiConsent":
    "اختیاری AI وضاحت شامل کریں (صرف متن جاتا ہے — تصویریں کبھی نہیں)",
  "farm.submit": "تصویریں اپ لوڈ کریں",
  "farm.saving": "محفوظ ہو رہا ہے…",
  "farm.saveError": "جانچ محفوظ کرنے میں مسئلہ ہوا۔ دوبارہ کوشش کریں۔",
  "farm.areaError": "اپنا پائلٹ علاقہ منتخب کریں۔",
  "farm.dateError": "آخری آبپاشی کی تاریخ لکھیں یا “نہیں معلوم” منتخب کریں۔",
  "farm.configWarn":
    "لائیو کنفیگریشن دستیاب نہیں — محفوظ شدہ پائلٹ علاقوں کی فہرست استعمال ہو رہی ہے۔",

  /* -------------------------------------------------- growth stages */
  "stage.emergence": "ابھارنا (Emergence)",
  "stage.cri": "جڑ شروع ہونا (CRI)",
  "stage.tillering": "کلیں نکالنا",
  "stage.jointing": "گانٹھ بندھنا",
  "stage.booting": "بونٹ بھرنا",
  "stage.heading": "بیجڑ نکلنا",
  "stage.flowering": "پھولوں کا مرحلہ",
  "stage.milk": "دودھ والا مرحلہ",
  "stage.dough": "آٹے والا مرحلہ",
  "stage.maturity": "پختگی",

  /* ------------------------------------------------------- options */
  "soil.sandy": "ریتیلی",
  "soil.loamy": "دومنٹی",
  "soil.clayey": "چکنی",
  "moisture.dry": "خشک",
  "moisture.moist": "نمی",
  "moisture.wet": "گیلی",
  "drainage.good": "اچھی",
  "drainage.poor": "کمزور",
  "drainage.waterlogging": "پانی بھر جانا",
  "onset.today": "آج",
  "onset.recent": "پچھلے چند دن میں",
  "onset.over_a_week": "ہفتے سے پہلے",
  "onset.not_sure": "نہیں معلوم",
  "spreading.yes": "ہاں",
  "spreading.no": "نہیں",
  "spreading.not_sure": "نہیں معلوم",

  /* -------------------------------------------------------- symptoms */
  "symptom.yellowing": "پیلہ پن",
  "symptom.spots": "داغ",
  "symptom.wilting": "مرجھانا",
  "symptom.rust_like": "زنگ جیسے نشانے",
  "symptom.drying": "خشک ہونا",
  "symptom.insects": "کیرے نظر آ رہے ہیں",

  /* ------------------------------------------------------------- photo */
  "photo.title": "تصویر اپ لوڈ کریں",
  "photo.intro":
    "متاثر پتے کی صاف، روشن قریب سے تصویر لیں — JPEG یا PNG، 4 تک۔ تصویریں اختیاری ہیں: بغیر تصویر کے بھی جاری رکھ سکتے ہیں۔",
  "photo.chooseLabel": "تصویریں",
  "photo.dropHint": "تصویریں یہاں گھسیٹیں، یا منتخب کرنے کے لیے تچ کریں",
  "photo.empty":
    "ابھی کوئی تصویر نہیں — یہ بالکل ٹھیک ہے۔ آپ بغیر تصویر کے جاری رکھ سکتے ہیں، کھیت کا منصوبہ پھر بھی ملے گا۔",
  "photo.typeLabel": "تصویر کی قسم",
  "photo.ready": "اپ لوڈ کے لیے تیار۔",
  "photo.uploading": "اپ لوڈ ہو رہا ہے…",
  "photo.uploadN": "{n} تصویریں اپ لوڈ کریں",
  "photo.uploadedN": "{n} تصویریں اپ لوڈ ہو گئیں۔",
  "photo.pass": "کوالٹی ٹھیک رہی۔ اپ لوڈ مکمل۔",
  "photo.fail":
    "کوالٹی درست نہیں — بصیرت شاید یہ تصویر نہ پڑھ سکے۔",
  "photo.retake":
    "دوبارہ لیں: پورے فریم میں متاثر پتا رکھیں، ہاتھ مستقر رکھیں، دن کی روشنی استعمال کریں، چمک سے بچیں۔",
  "photo.continue": "تجزیے کی طرف جائیں",
  "photo.errType": "صرف JPEG یا PNG ہے۔",
  "photo.errSize": "حجم کی حد سے بڑی ہے۔",
  "photo.errTooLarge":
    "تصویر بہت بڑی ہے۔ براہ کرم 4MB سے کم تصویر منتخب کریں۔",
  "photo.softQuality": "کم معیار کی تصویر — صرف ابتدائی جانچ کے لیے استعمال ہوگی۔",
  "photo.errMax": "ہر چیک میں {n} تصویریں تک۔",

  "view.symptom_closeup": "علامت کا قریب منظر (ترجیحاً)",
  "view.field_context": "کھیت کا ماحول",
  "view.whole_plant": "پورا پودا",
  "view.healthy_comparison": "صحت مند کی نقل",

  /* ---------------------------------------------------------- analysis */
  "analysis.title": "تجزیہ",
  "analysis.intro":
    "پانچ ایجنٹ موسم، پانی، فصل، تصویروں اور بازار کے ثبوت چیک کرتے ہیں — عام طور پر ایک منٹ میں۔",
  "analysis.progressTitle": "پیش رفت",
  "analysis.trackerTitle": "مراحل",
  "analysis.jobStatus": "جاب کی حالت",
  "analysis.notStarted":
    "تجزیہ ابھی شروع نہیں ہوا۔ “تجزیہ شروع کریں” دبائیں — نیچے کی پیش رفت براہ راست بیک اینڈ سے آتی ہے۔",
  "analysis.waitingFirst": "پہلے ایونٹ کا انتظار ہے…",
  "analysis.live": "ہر سیکنڈ تازہ رپورٹ آ رہی ہے…",
  "analysis.start": "تجزیہ شروع کریں",
  "analysis.starting": "شروع ہو رہا ہے…",
  "analysis.running": "تجزیہ جاری ہے…",
  "analysis.retry": "دوبارہ کوشش کریں",
  "analysis.retrying": "دوبارہ کوشش ہو رہی ہے…",
  "analysis.failed": "تجزیہ ناکام ہوا۔ آپ دوبارہ کوشش کر سکتے ہیں۔",
  "analysis.backPhotos": "تصویریں واپس",
  "analysis.rawEvents": "لائیو ایونٹ لاگ",

  "phase.quality_gate": "تصویر کوالٹی گیٹ",
  "phase.weather": "موسم چیک",
  "phase.vision": "وژن (تصویر) چیک",
  "phase.market": "بازار چیک",
  "phase.crop": "فصل چیک",
  "phase.water": "پانی چیک",
  "phase.policy_gate": "حفاظتی پالیسی گیٹ",
  "phase.farm_advisor": "کھیت کا منصوبہ بن رہا ہے",
  "phase.gemini_explanation": "AI وضاحت",
  "phase.analysis": "تجزیہ",

  "evstatus.started": "شروع",
  "evstatus.completed": "مکمل",
  "evstatus.unavailable": "دستیاب نہیں",
  "evstatus.failed": "ناکام",
  "evstatus.skipped": "چھوڑا گیا",

  /* ----------------------------------------------------------- results */
  "results.title": "نتائج",
  "results.intro":
    "یہ صرف ابتدائی رہنمائی ہے — ذیل کا منصوبہ حتمی تشخیص نہیں ہے۔",
  "results.loading": "نتائج لوڈ ہو رہے ہیں",
  "results.pending":
    "تجزیہ ابھی جاری ہے — جاب مکمل ہوتے ہی نتائج یہاں آئیں گے۔",
  "results.failed":
    "تجزیہ مکمل نہیں ہو سکا۔ تجزیے کی اسکرین سے دوبارہ کوشش کریں۔",
  "results.jobFailed":
    "تجزیہ جاب ناکام ہوئی۔ کچھ کارڈ نامکمل ہو سکتے ہیں۔",
  "results.backAnalysis": "تجزیے پر واپس",
  "results.retryAnalysis": "دوبارہ تجزیہ کریں",
  "results.startNew": "نیا چیک",
  "results.followup": "پیروی درج کریں",
  "results.errorEmpty":
    "نتائج لوڈ نہیں ہو سکے — اپنا کنکشن چیک کر کے دوبارہ کوشش کریں۔",

  /* -------------------------------------------------------- farm plan */
  "plan.title": "فارم پلان",
  "plan.fieldStatus": "کھیت کی حالت",
  "plan.checks": "ترجیحی چیکس",
  "plan.conflicts": "متناقض ثبوت",
  "plan.nextCheck": "اگلا چیک:",
  "plan.verification": "تصدیقی مرحلہ",
  "plan.policy": "پالیسی",
  "plan.empty":
    "اس چیک کا کوئی منصوبہ نہیں بنا — تجزیہ ناکام یا منقطع ہوا ہو سکتا ہے۔ منصوبہ بنانے کے لیے دوبارہ تجزیہ کریں۔",
  "plan.why": "وجہ:",
  "plan.watch": "کن باتوں پر نظر رکھیں:",

  /* ------------------------------------------------------ explanation */
  "exp.title": "وضاحت",
  "exp.unavailable": "وضاحت دستیاب نہیں",
  "exp.authoritative": "اوپر دیا گیا کھیت کا منصوبہ حتمی فیصلہ ہے۔",
  "exp.consent_missing": "وضاحت کی اجازت نہیں دی گئی",
  "exp.disabled": "وضاحت کی خدمت بند ہے",
  "exp.key_missing": "وضاحت کی کوئی کلید مقرر نہیں",
  "exp.timeout": "وضاحت کی خدمت کا وقت ختم ہو گیا",
  "exp.provider_error": "وضاحت کی خدمت میں خرابی",
  "exp.invalid_output": "وضاحت سے قابل استعمال جواب نہیں آیا",

  /* ------------------------------------------------------------ agents */
  "agent.weather": "موسم",
  "agent.water": "پانی",
  "agent.crop": "فصل",
  "agent.vision": "وژن (تصویر)",
  "agent.market": "مارکیٹ",
  "agent.empty":
    "اس ایجنٹ کی طرف سے ابھی کچھ نہیں — اس چیک میں کوئی مواد واپس نہیں آیا، اس لیے کچھ دکھایا نہیں جا رہا۔",
  "agent.evidence": "شواہد:",
  "agent.sources": "ذرائع",
  "agent.fieldChecks": "کھیت میں جانچ",
  "agent.evidenceSources": "شواہد اور ذرائع",
  "agent.safetyFlags": "حفاظتی نشانیاں",

  /* ------------------------------------- market quote (Punjab AMIS) */
  "market.quote.heading": "منڈی قیمت",
  "market.quote.market": "منڈی",
  "market.quote.commodity": "فصل",
  "market.quote.min": "کم از کم",
  "market.quote.max": "زیادہ سے زیادہ",
  "market.quote.average": "اوسط",
  "market.quote.unit": "اکائی",
  "market.quote.quoteDate": "قیمت کی تاریخ",
  "market.quote.retrieved": "وصول کیا گیا",
  "market.quote.source": "ذریعہ",
  "market.quote.sourceName": "Punjab AMIS",
  "market.quote.dateUnavailable": "تاریخ دستیاب نہیں",
  "market.freshness.fresh": "تازہ (۲۴ گھنٹے کے اندر)",
  "market.freshness.stale": "پرانا (۲۴ گھنٹے سے زیادہ)",
  "market.freshness.unknown": "تاریخ دستیاب نہیں",
  "market.unavailable":
    "لائیو گندم منڈی قیمت دستیاب نہیں۔ مقامی مارکیٹ کمیٹی سے تازہ ریٹ معلوم کریں یا اپنا ریٹ درج کریں۔",

  /* ------------------------- weather / water structured results panels */
  "weather.panel.heading": "پیشگویی کی قدریں",
  "weather.panel.gridNote": "پرووائیڈر کی پیشگویی گرڈ — اس کھیت کی پیمائش نہیں",
  "weather.panel.notReported": "دستیاب نہیں",
  "weather.panel.temperature": "درجہ حرارت (°C)",
  "weather.panel.humidity": "ہوا میں نمی (%)",
  "weather.panel.precipitation": "موجودہ بارش (mm)",
  "weather.panel.wind": "ہوا کی رفتار (km/h)",
  "weather.panel.next24Precip": "اگلے 24 گھنٹے کی بارش (mm)",
  "weather.panel.next24Prob": "اگلے 24 گھنٹے کا بارش کا امکان (%)",
  "weather.panel.provider": "پرووائیڈر",
  "weather.panel.providerTime": "پرووائیڈر کا وقت",
  "weather.panel.retrieved": "وصول کیا گیا",
  "weather.panel.freshness.fresh": "تازہ",
  "weather.panel.freshness.stale": "پرانا / وقت غائب",
  "weather.panel.freshness.unavailable": "دستیاب نہیں",
  "water.field.heading": "کھیت کی معلومات",
  "water.field.growthStage": "نمو کا مرحلہ",
  "water.field.irrigationHistory": "آخری آبپاشی",
  "water.field.soilTexture": "مٹی کی قسم",
  "water.field.soilMoisture": "مٹی کی نمی",
  "water.field.drainage": "نکاسی",
  "water.field.weatherContext": "موسم کا سیاق",
  "water.field.state.known": "معلوم",
  "water.field.state.unknown": "نامعلوم",
  "water.field.state.fresh": "تازہ",
  "water.field.state.stale": "پرانا",
  "water.field.state.unavailable": "دستیاب نہیں",
  "water.context.field_check_needed": "کھیت کی جانچ درکار ہے",
  "water.context.watch_drainage": "نکاسی پر نظر رکھیں",
  "water.context.forecast_context_only": "پیشگویی صرف سیاق ہے",

  /* ------------------------------------------- vision low-quality notices */
  "vision.soft.title": "کم معیار تصویر — ابتدائی ظاہری علامات کا جائزہ",
  "vision.soft.hint": "ممکن ہو تو پتے کی قریب سے اور واضح تصویر دوبارہ لیں۔",
  "vision.blocked.title": "تصویر کی جانچ نہیں ہو سکی",
  "vision.blocked.hint": "کسان کی بتائی گئی علامات کے ساتھ آگے بڑھیں۔",

  /* ---------------------------------------------------------- statuses */
  "status.complete": "مکمل",
  "status.partial": "جزوی",
  "status.unavailable": "دستیاب نہیں",
  "status.stale": "پرانا",
  "status.not_assessed": "جانچ نہیں ہو سکی",
  "status.unsupported": "غیر موزوں",
  "status.error": "خرابی",
  "status.pending": "زیرِ کار",
  "status.monitor": "نگرانی",
  "status.insufficient_information": "ناکافی معلومات",
  "status.field_inspection_recommended": "کھیت کا معائنہ سفارش ہے",
  "status.expert_review_recommended": "ماہر سے مشورہ تجویز کیا جاتا ہے",
  "status.queued": "قطار میں",
  "status.running": "جاری",
  "status.succeeded": "کامیاب",
  "status.failed": "ناکام",

  /* ----------------------------------------------------------- safety */
  "safety.banner":
    "یہ تصویری نتیجہ صرف اسکریننگ مدد ہے، تصدیق شدہ تشخیص نہیں۔ عمل سے پہلے اپنے تعلیمی مرکز کے ماہر سے رجوع کریں۔",

  /* ---------------------------------------------------------- followup */
  "fu.title": "پیروی",
  "fu.intro":
    "پیروی نیا مشاہدہ وقت کے ساتھ محفوظ کرتی ہے۔ یہ ثابت نہیں کرتا کہ حالت بڑھی یا ٹھیک ہوئی۔",
  "fu.cardTitle": "آپ نے کیا دیکھا؟",
  "fu.noteLabel": "مشاہدہ",
  "fu.noteHint":
    "1–1500 حروف۔ پچھلے چیک سے کیا بدلے ہیں وہ لکھیں۔",
  "fu.completionLegend": "کیا آپ نے چیکس مکمل کیے؟",
  "fu.completed": "مکمل",
  "fu.partially": "جزوی طور پر",
  "fu.notCompleted": "نہیں کیے",
  "fu.save": "پیروی محفوظ کریں",
  "fu.saving": "محفوظ ہو رہا ہے…",
  "fu.noteError": "اپنا مشاہدہ لکھیں۔",
  "fu.saveError": "پیروی محفوظ نہیں ہو سکی۔",
  "fu.back": "نتائج پر واپس",

  /* --------------------------------------------------------- settings */
  "set.title": "ترتیبات",
  "set.intro": "اس ڈیوائس کے لیے زبان اور رننگ معلومات۔",
  "set.language": "زبان",
  "set.aboutTitle": "اس ڈیپلائیمنٹ کے بارے میں",
  "set.safetyTitle": "تحذیر",
  "set.retention": "ڈیٹا برقرار رکھنے کی مدت:",
  "set.visionMode": "بصیرت موڈ:",
  "set.policy": "پالیسی ورژن:",
  "set.api": "API ورژن:",
  "set.hours": "گھنٹے",

  /* ------------------------------------------------------------- team */
  "team.title": "ہماری ٹیم",
  "team.tagline":
    "کسانOS کے پیچھے تعلیمی طلبہ — بہاولپور گندم پائلٹ کے لیے تحقیق، مخصوص ایجنٹس اور ڈیپلوائمنٹ۔",
  "team.leader": "ٹیم لیڈر",
  "team.leader.title": "اے آئی انجینئر اور سافٹ ویئر انجینئر",
  "team.leader.desc":
    "حسنین احمد KisanOS کی قیادت کرتے ہیں اور AI انجینئرنگ، فل اسٹیک ڈیولپمنٹ، پروڈکٹ آرکیٹیکچر اور کسانوں کے لیے مکمل تجربے پر کام کرتے ہیں۔ انہوں نے موسم، پانی، فصل، وژن اور مارکیٹ ایجنٹس پر مشتمل ملٹی ایجنٹ بیک اینڈ کو مربوط کیا۔",
  "team.desc.sharjeel":
    "واٹر ایجنٹ کی ہماہنگی — ہر چیک کے لیے کھیت کے ڈیٹا کا جائزہ، آبپاشی کی رہنمائی اور ثبوت کی فراہمی۔",
  "team.desc.minahil":
    "موسم ایجنٹ کی ہماہنگی — پیشگوئیاں، اخطارات اور پروجیکٹ کی پریزنٹیشن سلائیڈز۔",
  "team.desc.laraib":
    "فصل ایجنٹ کی ہماہنگی — زرعہ نوٹس، سفارشات کی تیاری اور پروجیکٹ دستاویزات۔",
  "team.desc.ghulam":
    "ویژن ایجنٹ کی ہماہنگی — تصویری اسکریننگ کے معیار، ڈیٹا سیٹس اور پائپ لائن ٹیسٹنگ۔",
  "team.desc.durdana":
    "مارکیٹ ایجنٹ کی ہماہنگی — قیمتوں کے اشارے، مارکیٹ کے رجحانات اور رپورٹس کی فراہمی۔",
  "team.pill.research": "تحقیق",
  "team.pill.coordination": "ہماہنگی",
  "team.pill.ai": "اے آئی انجینئرنگ",
  "team.pill.fullstack": "فل اسٹیک",
  "team.pill.backend": "بیک اینڈ",
  "team.pill.frontend": "فرنٹ اینڈ",
  "team.pill.deployment": "ڈیپلوائمنٹ",
  "team.pill.workflow": "پروجیکٹ ورک فلو",
  "team.pill.slides": "سلائیڈز",
  "team.pill.docs": "دستاویزات",
  "team.pill.water": "پانی ایجنٹ",
  "team.pill.weather": "موسم ایجنٹ",
  "team.pill.crop": "فصل ایجنٹ",
  "team.pill.vision": "ویژن ایجنٹ",
  "team.pill.market": "مارکیٹ ایجنٹ",
  "team.linkedin": "LinkedIn",

  /* ------------------------------------ results: untranslated backend text */
  "results.originalText": "اصل نظامی پیغام (English)",

  /* -------------------------------------------------- evidence & sources */
  "ev.band.low": "کم",
  "ev.band.medium": "درمیانہ",
  "ev.band.high": "زیادہ",
  "ev.band.not_calibrated": "مقامی طور پر تصدیق شدہ نہیں",

  "ev.label.farmer_reported": "کسان کی بتائی ہوئی",
  "ev.label.photo_visible": "تصویر میں نظر آنے والی",
  "ev.label.rule_based_check": "اعدالے پر مبنی جانچ",
  "ev.label.crop": "فصل",
  "ev.label.water": "پانی",
  "ev.label.vision": "وژن (تصویر)",

  "ev.src.official": "سرکاری",
  "ev.src.supporting": "معاون",
  "ev.src.secondary": "ثانوی",
  "ev.src.unverified": "تصدیق شدہ نہیں",
  "ev.src.farmer_reported": "کسان کی بتائی ہوئی",
  "ev.src.not_applicable": "لا اطلاق",

  /* --------------------------------------------------------- conflict topics */
  "plan.topic.field_moisture": "کھیت کی مٹی کی نمی",
  "plan.topic.field_moisture_vs_weather": "مٹی کی نمی اور موسم کی مطابقت",
  "plan.topic.weather_freshness": "موسمی ڈیٹا کی تازگی",
  "plan.topic.crop_vision_disagreement": "فصل اور وژن میں عدم اتفاق",

  /* ------------------------------------------- backend safety flag tokens */
  "flag.low_quality_image": "کم معیار کی تصویر",
  "flag.low_confidence": "کم اعتماد",
  "flag.retake_recommended": "تصویر دوبارہ لینے کی تجویز",
  "flag.not_a_diagnosis": "یہ تشخیص نہیں",
  "flag.local_validation_pending": "مقامی تصدیق زیرِ التواء ہے",
  "flag.confidence_capped_at_medium": "اعتماد زیادہ سے زیادہ درمیانہ",
  "flag.photo_quality_failed": "تصویر کا معیار درست نہیں",
  "flag.no_visual_analysis_performed": "کوئی بصری تجزیہ نہیں ہوا",
  "flag.manual_fallback_available": "دستی متبادل دستیاب ہے",
  "flag.model_unavailable": "ماڈل دستیاب نہیں",
  "flag.invalid_output_rejected": "ناقابل استعمال جواب مسترد",
  "flag.no_dummy_output_used": "کوئی بناوٹی جواب استعمال نہیں ہوا",
  "flag.wheat_scope_gate": "گندم کے دائرۂ کار کی پابندی",
  "flag.no_interpretation_accepted": "کوئی تفسیر قبول نہیں ہوئی",
  "flag.unsafe_model_text_rejected": "غیر محفوظ ماڈل متن مسترد",
  "flag.unsupported_scope": "غیر موزوں دائرۂ کار",
  "flag.unsupported_crop_scope": "غیر موزوں فصل کا دائرۂ کار",
  "flag.not_field_sensor": "یہ کھیت کا سینسر نہیں",
  "flag.no_crop_thresholds_applied": "کوئی فصل کی حد لاں نہیں گئی",
  "flag.no_simulated_weather_fallback": "نمائشی موسم کا متبادل استعمال نہیں ہوا",
  "flag.weather_not_used_for_water": "موسم پانی کے فیصلوں کے لیے استعمال نہیں ہوا",
  "flag.weather_provenance_missing": "موسمی ڈیٹا کا ماخذ موجود نہیں",
  "flag.crop_rules_unverified": "فصل کے ااعدالے تصدیق شدہ نہیں",
  "flag.no_chemical_guidance": "کوئی کیمیائی رہنمائی نہیں",
  "flag.agent_error_isolated": "ایجنٹ کی خرابی الگ کر دی گئی",
  "flag.stale_quote": "پرانی قیمت",
  "flag.not_official_market_data": "سرکاری مارکیٹ ڈیٹا نہیں",
  "flag.farmer_reported_only": "صرف کسان کی بتائی ہوئی",
  "flag.simulated_demo_data": "نمائشی ڈیٹا",
  "flag.no_price_invented": "کوئی قیمت گھڑی نہیں گئی",
  "flag.adapter_payload_not_used": "ایڈاپٹر کا مواد استعمال نہیں ہوا",
  "flag.amis_source_reported": "AMIS کی طرف سے قیمت بتائی گئی",
  "flag.amis_unavailable": "AMIS سے قیمت حاصل نہ ہو سکی",
  "flag.source_date_missing": "ذریعے کی تاریخ دستیاب نہیں",
  "flag.market_name_missing": "بازار کا نام موجود نہیں",
  "flag.value_not_a_number": "قیمت عدد نہیں ہے",
  "flag.value_not_positive": "قیمت مثبت نہیں ہے",
  "flag.value_out_of_range": "قیمت مقررہ حد سے باہر ہے",
  "flag.unit_missing": "اکائی موجود نہیں",
  "flag.no_irrigation_command": "کوئی آبپاشی کا حکم نہیں",
  "flag.no_unapproved_numeric_thresholds": "کوئی غیر منظور شدہ عددی حد نہیں",
  "flag.forecast_not_effective_recharge": "پیشگوئی مؤثر پانی کی بھرائی نہیں",
  "flag.weather_not_used_or_not_fresh": "موسم استعمال نہیں ہوا یا تازہ نہیں",
  "flag.drainage_or_saturation_inspection": "نکاسی یا گیلے ہونے کا معائنہ",
  "flag.field_context_incomplete": "کھیت کی معلومات نامکمل",
  "flag.sowing_context_recorded_not_used_as_threshold":
    "بائی کا مواد حد کے طور پر استعمال نہیں ہوا",
  "flag.observed_at_missing": "قیمت کا مشاہدے کا وقت موجود نہیں",
  "flag.observed_at_invalid": "مشاہدے کا وقت درست نہیں",
  "flag.observed_at_timezone_missing": "مشاہدے کے وقت کا وقتی علاقہ موجود نہیں",
  "flag.observed_at_future": "مشاہدے کا وقت مستقبل میں ہے",
  "flag.quote_not_an_object": "قیمت کی ساخت درست نہیں",
  "flag.example_output_not_real_analysis": "مثال ہے، حقیقی تجزیہ نہیں",
  "flag.ai_output_rejected": "AI کا جواب مسترد ہوا",
  "flag.ai_enhancement_unavailable": "AI تیاری دستیاب نہیں",
};

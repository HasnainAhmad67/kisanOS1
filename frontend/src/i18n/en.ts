/**
 * English UI dictionary — the source of truth for translation keys.
 * `ur.ts` must implement every key (typed as Record<DictKey, string>),
 * so a missing Urdu translation is a TypeScript error.
 */
export const en = {
  /* ------------------------------------------------------------- common */
  "common.back": "Back",
  "common.loading": "Loading…",
  "common.tryAgain": "Try again",
  "common.remove": "Remove",
  "common.notSure": "Not sure",
  "common.known": "Known",

  /* ------------------------------------------------------- navigation */
  "nav.newCheck": "New Check",
  "nav.myChecks": "My Checks",
  "nav.guidance": "Guidance",
  "nav.settings": "Settings",
  "nav.team": "Team",
  "nav.main": "Main navigation",

  /* ------------------------------------------------------------- shell */
  "app.skip": "Skip to content",
  "app.langLabel": "Language",
  "app.footer":
    "KisanOS · Bahawalpur wheat pilot — screening support only, not a confirmed diagnosis.",

  /* ----------------------------------------------------------- welcome */
  "welcome.greeting": "Welcome",
  "welcome.title": "New field check",
  "welcome.tagline": "AI decision support for farmers",
  "welcome.intro":
    "Tell us what you are seeing in your wheat field, add a couple of photos, and get a short plan of what to check next — in a few minutes.",
  "welcome.howTitle": "How it works",
  "welcome.how1": "Answer a few questions about your field.",
  "welcome.how2": "Take close-up photos of the affected leaves.",
  "welcome.how3":
    "Review the five agent cards (weather, water, crop, vision, market) and your farm plan.",
  "welcome.safetyTitle": "Safety notice",
  "welcome.configLoading": "Loading live configuration…",
  "welcome.configUnavailable": "Live configuration unavailable",
  "welcome.crop": "Crop:",
  "welcome.areas": "Pilot areas:",
  "welcome.cta": "Start a new check",

  /* ------------------------------------------------------ farm details */
  "farm.title": "Farm details",
  "farm.intro":
    "Fields marked with * are required. Everything else can be “not sure”.",
  "farm.cropLegend": "Crop",
  "farm.cropHint": "The pilot supports wheat only.",
  "farm.cropConfirm": "I confirm this field is wheat",
  "farm.areaLabel": "Area",
  "farm.areaPlaceholder": "Select your pilot area",
  "farm.areaLoading": "Loading areas…",
  "farm.areaConfirmLegend": "Area confirmation",
  "farm.areaConfirm": "I confirm this Bahawalpur pilot area",
  "farm.growthLabel": "Growth stage",
  "farm.irrigationLabel": "Irrigation history",
  "farm.lastIrrigation": "Last irrigation date",
  "farm.soilTexture": "Soil texture",
  "farm.soilMoisture": "Soil moisture (by hand)",
  "farm.drainage": "Drainage",
  "farm.onsetLabel": "When did symptoms start?",
  "farm.spreadingLegend": "Are symptoms spreading?",
  "farm.symptomsLegend": "Symptoms you can see",
  "farm.symptomsHint": "Select at least one.",
  "farm.symptomsError": "Select at least one symptom you can see.",
  "farm.notesLabel": "Notes",
  "farm.notesHint": "Up to 1500 characters. Optional.",
  "farm.privacyLegend": "Privacy",
  "farm.privacyHint":
    "Consent is required to save an assessment. GPS coordinates are not collected.",
  "farm.consent":
    "I agree to save this assessment and its photos for my own use",
  "farm.geminiConsent":
    "Add the optional AI explanation (sends text — never photos — to Gemini)",
  "farm.submit": "Continue to photos",
  "farm.saving": "Saving…",
  "farm.saveError": "Something went wrong saving the assessment. Try again.",
  "farm.areaError": "Select your pilot area.",
  "farm.dateError": "Enter the last irrigation date, or choose “Not sure”.",
  "farm.configWarn":
    "Live configuration unavailable — using the saved pilot-area list.",

  /* -------------------------------------------------- growth stages */
  "stage.emergence": "Emergence",
  "stage.cri": "Crown root initiation (CRI)",
  "stage.tillering": "Tillering",
  "stage.jointing": "Jointing",
  "stage.booting": "Booting",
  "stage.heading": "Heading",
  "stage.flowering": "Flowering",
  "stage.milk": "Milk",
  "stage.dough": "Dough",
  "stage.maturity": "Maturity",

  /* ------------------------------------------------------- options */
  "soil.sandy": "Sandy",
  "soil.loamy": "Loamy",
  "soil.clayey": "Clayey",
  "moisture.dry": "Dry",
  "moisture.moist": "Moist",
  "moisture.wet": "Wet",
  "drainage.good": "Good",
  "drainage.poor": "Poor",
  "drainage.waterlogging": "Waterlogging",
  "onset.today": "Today",
  "onset.recent": "Within the last few days",
  "onset.over_a_week": "Over a week ago",
  "onset.not_sure": "Not sure",
  "spreading.yes": "Yes",
  "spreading.no": "No",
  "spreading.not_sure": "Not sure",

  /* -------------------------------------------------------- symptoms */
  "symptom.yellowing": "Yellowing",
  "symptom.spots": "Spots",
  "symptom.wilting": "Wilting",
  "symptom.rust_like": "Rust-like marks",
  "symptom.drying": "Drying",
  "symptom.insects": "Insects visible",

  /* ------------------------------------------------------------- photo */
  "photo.title": "Upload photos",
  "photo.intro":
    "Add a sharp, well-lit close-up of an affected leaf — JPEG or PNG, up to 4 photos. Photos are optional: you can continue without them.",
  "photo.chooseLabel": "Photos",
  "photo.dropHint": "Drag photos here, or tap to choose",
  "photo.empty":
    "No photos yet — that is OK. You can continue without photos and still get your farm plan.",
  "photo.typeLabel": "Photo type",
  "photo.ready": "Ready to upload.",
  "photo.uploading": "Uploading…",
  "photo.uploadN": "Upload {n} photo(s)",
  "photo.uploadedN": "{n} photo(s) uploaded.",
  "photo.pass": "Quality check passed. Uploaded.",
  "photo.fail":
    "Quality check failed — Vision may not read this photo.",
  "photo.retake":
    "Retake: fill the frame with the affected leaf, hold steady, use daylight, avoid glare.",
  "photo.continue": "Continue to Analysis",
  "photo.errType": "is JPEG or PNG only.",
  "photo.errSize": "is larger than the size limit.",
  "photo.errTooLarge":
    "Photo is too large. Please select a photo under 4MB.",
  "photo.softQuality": "Low-quality photo — used for a preliminary check only.",
  "photo.errMax": "Only {n} photos per check.",

  "view.symptom_closeup": "Symptom close-up (preferred)",
  "view.field_context": "Field context",
  "view.whole_plant": "Whole plant",
  "view.healthy_comparison": "Healthy comparison",

  /* ---------------------------------------------------------- analysis */
  "analysis.title": "Analysis",
  "analysis.intro":
    "Five agents check weather, water, crop, photos, and market evidence — usually within a minute.",
  "analysis.progressTitle": "Progress",
  "analysis.trackerTitle": "Phase tracker",
  "analysis.jobStatus": "Job status",
  "analysis.notStarted":
    "The analysis has not started yet. Press Start Analysis — progress below comes straight from the backend job.",
  "analysis.waitingFirst": "Waiting for the first backend event…",
  "analysis.live": "Live backend updates every second…",
  "analysis.start": "Start Analysis",
  "analysis.starting": "Starting…",
  "analysis.running": "Analysis running…",
  "analysis.retry": "Retry Analysis",
  "analysis.retrying": "Retrying…",
  "analysis.failed": "Analysis failed. You can retry.",
  "analysis.backPhotos": "Back to photos",
  "analysis.rawEvents": "Live event log",

  "phase.quality_gate": "Photo quality gate",
  "phase.weather": "Weather check",
  "phase.vision": "Photo (vision) check",
  "phase.market": "Market check",
  "phase.crop": "Crop check",
  "phase.water": "Water check",
  "phase.policy_gate": "Safety policy gate",
  "phase.farm_advisor": "Building farm plan",
  "phase.gemini_explanation": "AI explanation",
  "phase.analysis": "Analysis",

  "evstatus.started": "started",
  "evstatus.completed": "completed",
  "evstatus.unavailable": "unavailable",
  "evstatus.failed": "failed",
  "evstatus.skipped": "skipped",

  /* ----------------------------------------------------------- results */
  "results.title": "Results",
  "results.intro":
    "Screening support only — the plan below is not a confirmed diagnosis.",
  "results.loading": "Loading results",
  "results.pending":
    "Analysis is still running — results appear here once the job finishes.",
  "results.failed":
    "The analysis did not finish. Retry it from the analysis screen.",
  "results.jobFailed":
    "The analysis job reported a failure. Some cards may be incomplete.",
  "results.backAnalysis": "Back to analysis",
  "results.retryAnalysis": "Retry analysis",
  "results.startNew": "Start New Check",
  "results.followup": "Record a follow-up",
  "results.errorEmpty":
    "Results could not be loaded — check your connection and try once more.",

  /* -------------------------------------------------------- farm plan */
  "plan.title": "Farm Plan",
  "plan.fieldStatus": "Field status",
  "plan.checks": "Prioritized checks",
  "plan.conflicts": "Conflicting evidence",
  "plan.nextCheck": "Next check:",
  "plan.verification": "Verification step",
  "plan.policy": "Policy",
  "plan.empty":
    "No farm plan was produced for this check — the analysis may have failed or been interrupted. Retry the analysis to build a plan.",
  "plan.why": "Why:",
  "plan.watch": "Watch for:",

  /* ------------------------------------------------------ explanation */
  "exp.title": "Explanation",
  "exp.unavailable": "Explanation unavailable",
  "exp.authoritative": "The farm plan above stays authoritative.",
  "exp.consent_missing": "explanation consent was not given",
  "exp.disabled": "the explanation service is switched off",
  "exp.key_missing": "no explanation key is configured",
  "exp.timeout": "the explanation service timed out",
  "exp.provider_error": "the explanation provider had an error",
  "exp.invalid_output": "the explanation returned unusable output",

  /* ------------------------------------------------------------ agents */
  "agent.weather": "Weather",
  "agent.water": "Water",
  "agent.crop": "Crop",
  "agent.vision": "Vision (photo)",
  "agent.market": "Market",
  "agent.empty":
    "Nothing from this agent yet — no data has been returned for this check, so nothing is shown.",
  "agent.evidence": "Evidence:",
  "agent.sources": "Sources",
  "agent.fieldChecks": "Field checks",
  "agent.evidenceSources": "Evidence & sources",
  "agent.safetyFlags": "Safety flags",

  /* ------------------------------------- market quote (Punjab AMIS) */
  "market.quote.heading": "Mandi quote",
  "market.quote.market": "Market",
  "market.quote.commodity": "Commodity",
  "market.quote.min": "Min",
  "market.quote.max": "Max",
  "market.quote.average": "Average",
  "market.quote.unit": "Unit",
  "market.quote.quoteDate": "Quote date",
  "market.quote.retrieved": "Retrieved at",
  "market.quote.source": "Source",
  "market.quote.sourceName": "Punjab AMIS",
  "market.quote.dateUnavailable": "date unavailable",
  "market.freshness.fresh": "Fresh (within 24 hours)",
  "market.freshness.stale": "Stale (older than 24 hours)",
  "market.freshness.unknown": "Date unavailable",
  "market.unavailable":
    "A live wheat mandi price is not available. Ask your local market committee for today's rate, or enter your own rate.",

  /* ------------------------- weather / water structured results panels */
  "weather.panel.heading": "Forecast values",
  "weather.panel.gridNote":
    "provider forecast grid — not a measurement from this field",
  "weather.panel.notReported": "not reported",
  "weather.panel.temperature": "Temperature (°C)",
  "weather.panel.humidity": "Relative humidity (%)",
  "weather.panel.precipitation": "Current precipitation (mm)",
  "weather.panel.wind": "Wind speed (km/h)",
  "weather.panel.next24Precip": "Next 24 h precipitation (mm)",
  "weather.panel.next24Prob": "Next 24 h rain probability (%)",
  "weather.panel.provider": "Provider",
  "weather.panel.providerTime": "Provider time",
  "weather.panel.retrieved": "Retrieved at",
  "weather.panel.freshness.fresh": "Fresh",
  "weather.panel.freshness.stale": "Stale / time missing",
  "weather.panel.freshness.unavailable": "Unavailable",
  "water.field.heading": "Field information",
  "water.field.growthStage": "Growth stage",
  "water.field.irrigationHistory": "Last irrigation",
  "water.field.soilTexture": "Soil texture",
  "water.field.soilMoisture": "Soil moisture",
  "water.field.drainage": "Drainage",
  "water.field.weatherContext": "Weather context",
  "water.field.state.known": "Known",
  "water.field.state.unknown": "Unknown",
  "water.field.state.fresh": "Fresh",
  "water.field.state.stale": "Stale",
  "water.field.state.unavailable": "Unavailable",
  "water.context.field_check_needed": "Field check needed",
  "water.context.watch_drainage": "Watch drainage",
  "water.context.forecast_context_only": "Forecast is context only",

  /* ------------------------------------------- vision low-quality notices */
  "vision.soft.title": "Low-quality photo — preliminary visible-sign check",
  "vision.soft.hint": "Please retake a clearer close-up when possible.",
  "vision.blocked.title": "Photo could not be assessed",
  "vision.blocked.hint": "Continue using farmer-reported symptoms.",

  /* ---------------------------------------------------------- statuses */
  "status.complete": "complete",
  "status.partial": "partial",
  "status.unavailable": "unavailable",
  "status.stale": "stale",
  "status.not_assessed": "not assessed",
  "status.unsupported": "unsupported",
  "status.error": "error",
  "status.pending": "pending",
  "status.monitor": "monitor",
  "status.insufficient_information": "insufficient information",
  "status.field_inspection_recommended": "field inspection recommended",
  "status.expert_review_recommended": "expert review recommended",
  "status.queued": "queued",
  "status.running": "running",
  "status.succeeded": "succeeded",
  "status.failed": "failed",

  /* ----------------------------------------------------------- safety */
  "safety.banner":
    "This screening result is only support for screening — it is not a confirmed diagnosis. Show it to an extension adviser before acting.",

  /* ---------------------------------------------------------- followup */
  "fu.title": "Follow-up",
  "fu.intro":
    "A follow-up saves a new timestamped observation. It never proves that a condition progressed or healed.",
  "fu.cardTitle": "What did you observe?",
  "fu.noteLabel": "Observation",
  "fu.noteHint":
    "1–1500 characters. Say what changed since the last check.",
  "fu.completionLegend": "Did you complete the checks?",
  "fu.completed": "Completed",
  "fu.partially": "Partially",
  "fu.notCompleted": "Not completed",
  "fu.save": "Save follow-up",
  "fu.saving": "Saving…",
  "fu.noteError": "Write what you observed.",
  "fu.saveError": "Could not save the follow-up.",
  "fu.back": "Back to results",

  /* --------------------------------------------------------- settings */
  "set.title": "Settings",
  "set.intro": "Language and runtime information for this device.",
  "set.language": "Language",
  "set.aboutTitle": "About this deployment",
  "set.safetyTitle": "Safety notice",
  "set.retention": "Data retention:",
  "set.visionMode": "Vision mode:",
  "set.policy": "Policy version:",
  "set.api": "API version:",
  "set.hours": "hours",

  /* ------------------------------------------------------------- team */
  "team.title": "Our Team",
  "team.tagline":
    "The students behind KisanOS — research, specialist agents, and deployment for the Bahawalpur wheat pilot.",
  "team.leader": "Team Leader",
  "team.leader.title": "AI Engineer & Software Engineer",
  "team.leader.desc":
    "Hasnain Ahmad leads KisanOS, driving AI engineering, full-stack development, product architecture, and the end-to-end farmer experience. He integrated the multi-agent backend spanning Weather, Water, Crop, Vision, and Market intelligence.",
  "team.desc.sharjeel":
    "Coordinates the Water Agent — field data review, irrigation insights, and evidence sourcing for every check.",
  "team.desc.minahil":
    "Coordinates the Weather Agent — forecasts, alerts, and the project's slide decks.",
  "team.desc.laraib":
    "Coordinates the Crop Agent — agronomy notes, recommendation drafting, and project documentation.",
  "team.desc.ghulam":
    "Coordinates the Vision Agent — photo screening quality, datasets, and pipeline testing.",
  "team.desc.durdana":
    "Coordinates the Market Agent — price signals, market trends, and report delivery.",
  "team.pill.research": "Research",
  "team.pill.coordination": "Coordination",
  "team.pill.ai": "AI Engineering",
  "team.pill.fullstack": "Full-Stack",
  "team.pill.backend": "Backend",
  "team.pill.frontend": "Frontend",
  "team.pill.deployment": "Deployment",
  "team.pill.workflow": "Project Workflow",
  "team.pill.slides": "Slides",
  "team.pill.docs": "Docs",
  "team.pill.water": "Water Agent",
  "team.pill.weather": "Weather Agent",
  "team.pill.crop": "Crop Agent",
  "team.pill.vision": "Vision Agent",
  "team.pill.market": "Market Agent",
  "team.linkedin": "LinkedIn",

  /* ------------------------------------ results: untranslated backend text */
  "results.originalText": "Original system message (English)",

  /* -------------------------------------------------- evidence & sources */
  "ev.band.low": "low",
  "ev.band.medium": "medium",
  "ev.band.high": "high",
  "ev.band.not_calibrated": "not calibrated",

  "ev.label.farmer_reported": "farmer_reported",
  "ev.label.photo_visible": "photo_visible",
  "ev.label.rule_based_check": "rule_based_check",
  "ev.label.crop": "crop",
  "ev.label.water": "water",
  "ev.label.vision": "vision",

  "ev.src.official": "official",
  "ev.src.supporting": "supporting",
  "ev.src.secondary": "secondary",
  "ev.src.unverified": "unverified",
  "ev.src.farmer_reported": "farmer reported",
  "ev.src.not_applicable": "not applicable",

  /* --------------------------------------------------------- conflict topics
   * English values keep the backend's raw topic ids so English renders
   * exactly as before. */
  "plan.topic.field_moisture": "field_moisture",
  "plan.topic.field_moisture_vs_weather": "field_moisture_vs_weather",
  "plan.topic.weather_freshness": "weather_freshness",
  "plan.topic.crop_vision_disagreement": "crop_vision_disagreement",

  /* ------------------------------------------- backend safety flag tokens
   * English keeps the raw token (unchanged rendering); Urdu translates. */
  "flag.low_quality_image": "low_quality_image",
  "flag.low_confidence": "low_confidence",
  "flag.retake_recommended": "retake_recommended",
  "flag.not_a_diagnosis": "not_a_diagnosis",
  "flag.local_validation_pending": "local_validation_pending",
  "flag.confidence_capped_at_medium": "confidence_capped_at_medium",
  "flag.photo_quality_failed": "photo_quality_failed",
  "flag.no_visual_analysis_performed": "no_visual_analysis_performed",
  "flag.manual_fallback_available": "manual_fallback_available",
  "flag.model_unavailable": "model_unavailable",
  "flag.invalid_output_rejected": "invalid_output_rejected",
  "flag.no_dummy_output_used": "no_dummy_output_used",
  "flag.wheat_scope_gate": "wheat_scope_gate",
  "flag.no_interpretation_accepted": "no_interpretation_accepted",
  "flag.unsafe_model_text_rejected": "unsafe_model_text_rejected",
  "flag.unsupported_scope": "unsupported_scope",
  "flag.unsupported_crop_scope": "unsupported_crop_scope",
  "flag.not_field_sensor": "not_field_sensor",
  "flag.no_crop_thresholds_applied": "no_crop_thresholds_applied",
  "flag.no_simulated_weather_fallback": "no_simulated_weather_fallback",
  "flag.weather_not_used_for_water": "weather_not_used_for_water",
  "flag.weather_provenance_missing": "weather_provenance_missing",
  "flag.crop_rules_unverified": "crop_rules_unverified",
  "flag.no_chemical_guidance": "no_chemical_guidance",
  "flag.agent_error_isolated": "agent_error_isolated",
  "flag.stale_quote": "stale_quote",
  "flag.not_official_market_data": "not_official_market_data",
  "flag.farmer_reported_only": "farmer_reported_only",
  "flag.simulated_demo_data": "simulated_demo_data",
  "flag.no_price_invented": "no_price_invented",
  "flag.adapter_payload_not_used": "adapter_payload_not_used",
  "flag.amis_source_reported": "amis_source_reported",
  "flag.amis_unavailable": "amis_unavailable",
  "flag.source_date_missing": "source_date_missing",
  "flag.market_name_missing": "market_name_missing",
  "flag.value_not_a_number": "value_not_a_number",
  "flag.value_not_positive": "value_not_positive",
  "flag.value_out_of_range": "value_out_of_range",
  "flag.unit_missing": "unit_missing",
  "flag.no_irrigation_command": "no_irrigation_command",
  "flag.no_unapproved_numeric_thresholds": "no_unapproved_numeric_thresholds",
  "flag.forecast_not_effective_recharge": "forecast_not_effective_recharge",
  "flag.weather_not_used_or_not_fresh": "weather_not_used_or_not_fresh",
  "flag.drainage_or_saturation_inspection": "drainage_or_saturation_inspection",
  "flag.field_context_incomplete": "field_context_incomplete",
  "flag.sowing_context_recorded_not_used_as_threshold":
    "sowing_context_recorded_not_used_as_threshold",
  "flag.observed_at_missing": "observed_at_missing",
  "flag.observed_at_invalid": "observed_at_invalid",
  "flag.observed_at_timezone_missing": "observed_at_timezone_missing",
  "flag.observed_at_future": "observed_at_future",
  "flag.quote_not_an_object": "quote_not_an_object",
  "flag.example_output_not_real_analysis": "example_output_not_real_analysis",
  "flag.ai_output_rejected": "ai_output_rejected",
  "flag.ai_enhancement_unavailable": "ai_enhancement_unavailable",
} as const;

export type DictKey = keyof typeof en;

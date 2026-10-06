/**
 * TypeScript mirrors of the KisanOS backend Pydantic schemas
 * (backend/app/schemas.py + response bodies in backend/app/api/routes.py).
 *
 * Datetimes are ISO-8601 strings as serialized by Pydantic's JSON mode.
 * Optional-with-default backend fields are typed optional here; fields the
 * backend requires stay required. `extra="forbid"` on the backend means no
 * unknown keys are ever sent.
 */

/* ------------------------------------------------------------------ enums */

export type Locale = "en" | "ur" | "roman_ur";

export type GrowthStage =
  | "emergence"
  | "cri"
  | "tillering"
  | "jointing"
  | "booting"
  | "heading"
  | "flowering"
  | "milk"
  | "dough"
  | "maturity"
  | "not_sure";

export type AreaCode =
  | "bahawalpur_sadar"
  | "ahmadpur_east"
  | "yazman"
  | "hasilpur"
  | "khairpur_tamewali";

export type SoilTexture = "sandy" | "loamy" | "clayey" | "not_sure";
export type SoilMoisture = "dry" | "moist" | "wet" | "not_sure";
export type Drainage = "good" | "poor" | "waterlogging" | "not_sure";
export type SymptomOnset = "today" | "recent" | "over_a_week" | "not_sure";
export type SymptomsSpreading = "yes" | "no" | "not_sure";
export type IrrigationHistory = "known" | "not_sure";

export type ViewType =
  | "symptom_closeup"
  | "field_context"
  | "whole_plant"
  | "healthy_comparison";

export type ConsentCompletion =
  | "completed"
  | "not_completed"
  | "partially_completed"
  | "not_sure";

/* ------------------------------------------------------------- assessment */

export interface FarmerMarketQuote {
  market: string;
  value: number;
  unit: "PKR/100kg" | "PKR/40kg" | "PKR/tonne" | "other";
  observed_at: string;
  note?: string | null;
  /** Demo/simulated quotes are always labelled as such by the Market Agent. */
  simulated?: boolean;
}

/** Body of POST /api/v1/assessments (backend `AssessmentCreate`). */
export interface AssessmentCreatePayload {
  crop: "wheat";
  crop_confirmed: boolean;
  area_code: AreaCode;
  area_confirmed: boolean;
  growth_stage?: GrowthStage;
  observed_at?: string;
  last_irrigation_date?: string | null;
  irrigation_history?: IrrigationHistory;
  sowing_date?: string | null;
  soil_texture?: SoilTexture;
  soil_moisture?: SoilMoisture;
  drainage?: Drainage;
  symptom_onset?: SymptomOnset;
  symptoms_spreading?: SymptomsSpreading;
  symptoms?: string[];
  notes?: string | null;
  locale?: Locale;
  timezone?: string;
  consent_given: boolean;
  consent_version: string;
  gemini_explanation_consent?: boolean;
  gps_consent?: boolean;
  latitude?: number | null;
  longitude?: number | null;
  market_quote?: FarmerMarketQuote | null;
}

/** Response of POST /api/v1/assessments (backend `AssessmentCreated`). */
export interface AssessmentCreated {
  assessment_id: string;
  access_token: string;
  created_at: string;
  required_photo_slots: string[];
  supported_areas: string[];
  policy_version: string;
  retention_hours: number;
  safety_notice: string;
}

/** Body of POST /api/v1/assessments/{id}/followups (backend `FollowUpCreate`). */
export interface FollowUpCreatePayload {
  note: string;
  check_ids?: string[];
  completion?: ConsentCompletion;
  observed_at?: string;
}

export interface FollowUpCreated {
  followup_id: string;
  assessment_id: string;
  created_at: string;
  note_saved: boolean;
  message: string;
}

/* ------------------------------------------------------------------ images */

/** Quality verdict from the team gate `app/team_agents/vision/quality.py`. */
export interface QualityVerdict {
  passed: boolean;
  issues: string[];
  /** Issues that hard-block inference (no model run). */
  hard_issues?: string[];
  /** Issues soft enough for a low-confidence screening run. */
  soft_issues?: string[];
  blur_score?: number;
  brightness?: number;
  plant_fraction?: number;
  [key: string]: unknown;
}

/** Response of POST /api/v1/assessments/{id}/images. */
export interface ImageUploadResponse {
  image_id: string;
  view_type: ViewType;
  mime_type: string;
  byte_size: number;
  sha256: string;
  dimensions: { width: number; height: number };
  quality: QualityVerdict;
  private_storage: boolean;
  exif_removed: boolean;
  retention_hours: number;
}

/* ---------------------------------------------------------------- analysis */

export interface AnalyzeAccepted {
  job_id: string;
  state: JobState;
  status_url: string;
  reused_active_job: boolean;
}

export type JobState =
  | "queued"
  | "running"
  | "succeeded"
  | "partial"
  | "failed";

export type JobEventStatus =
  | "started"
  | "completed"
  | "unavailable"
  | "failed"
  | "skipped";

/** Backend `JobEvent`. */
export interface JobEvent {
  sequence: number;
  phase: string;
  status: JobEventStatus;
  timestamp: string;
  detail: string | null;
}

/** Backend `JobStatus` — GET /api/v1/jobs/{job_id}. */
export interface JobStatus {
  job_id: string;
  assessment_id: string;
  state: JobState;
  events: JobEvent[];
  created_at: string;
  updated_at: string;
  error_code: string | null;
}

/* ------------------------------------------------------------- agent cards */

export type AgentId = "weather" | "water" | "crop" | "vision" | "market";

export type AgentStatus =
  | "complete"
  | "partial"
  | "unavailable"
  | "stale"
  | "not_assessed"
  | "unsupported"
  | "error";

export type EvidenceBand = "low" | "medium" | "high" | "not_calibrated";

export type SourceStatus =
  | "official"
  | "supporting"
  | "secondary"
  | "unverified"
  | "farmer_reported"
  | "not_applicable";

/** Backend `Source`. */
export interface Source {
  title: string;
  url: string | null;
  publisher: string;
  geography: string;
  published_at: string | null;
  retrieved_at: string | null;
  source_status: SourceStatus;
  note: string | null;
}

/** Backend `AgentResult`. */
export interface AgentResult {
  assessment_id: string;
  agent_id: AgentId;
  status: AgentStatus;
  summary: string;
  observations: string[];
  possible_causes: string[];
  checks: string[];
  evidence_band: EvidenceBand;
  evidence_reason: string;
  sources: Source[];
  provider_or_model: string;
  version: string;
  created_at: string;
  safety_flags: string[];
  data: Record<string, unknown>;
  input_evidence: string[];
}

export type QuoteFreshness = "fresh" | "stale" | "unknown";
/**
 * Official Punjab AMIS quote in `data.quote` (Market Agent). Every field comes
 * straight from the AMIS page: nothing is inferred, so `null` means the source
 * did not report it and must never be rendered as 0 or as a default.
 */
export interface AmisQuote {
  source: "AMIS";
  source_url: string;
  market: string;
  market_reported_by_source: string;
  commodity: string;
  currency: string;
  /** Exactly as the source states it (e.g. "Rs/100Kg"). */
  unit: string;
  min_price: number | null;
  max_price: number | null;
  average_price: number | null;
  /** Start of the AMIS source day (PKT) — null when the page gave no date. */
  quoted_at: string | null;
  source_date: string | null;
  retrieved_at: string;
  evidence_band: "medium" | "low";
  verification_status: "source_reported";
  freshness: QuoteFreshness;
}

/* ------------------------------------------------ weather + water cards */

/** `data.current` on the Weather card — provider values with explicit units. */
export interface WeatherCurrent {
  temperature_c: number | null;
  relative_humidity_pct: number | null;
  precipitation_mm: number | null;
  wind_speed_kmh: number | null;
  weather_code?: number | null;
}

/**
 * `data.next_24h` on the Weather card. Values are aggregated from the
 * provider's own hourly rows inside the window only; `null` means the series
 * was absent, never a synthesized 0.
 */
export interface WeatherNext24h {
  window_start: string | null;
  window_end: string | null;
  precipitation_total_mm: number | null;
  precipitation_probability_max_pct: number | null;
  hourly_samples?: number;
  basis?: string;
}

/** Fixed plain-language forecast context emitted by the Weather adapter. */
export interface WeatherForecastContext {
  precipitation_expected_next_24h: boolean | null;
  statements: string[];
}

/** `data` of the Weather card when the provider returned usable values. */
export interface WeatherCardData {
  provider?: string;
  location_name: string;
  location_granularity?: string;
  timezone?: string;
  provider_observation_at?: string | null;
  retrieved_at?: string | null;
  freshness?: string;
  current?: WeatherCurrent | null;
  next_24h?: WeatherNext24h | null;
  forecast_context?: WeatherForecastContext;
  daily_outlook?: unknown[];
  [key: string]: unknown;
}

/** Per-input state on the Water card — unknown inputs stay unknown. */
export type FieldInputState = "known" | "unknown";
export type WeatherContextState = "fresh" | "stale" | "unavailable";

export interface InputCompleteness {
  growth_stage: FieldInputState;
  irrigation_history: FieldInputState;
  soil_texture: FieldInputState;
  soil_moisture: FieldInputState;
  drainage: FieldInputState;
  weather_context: WeatherContextState;
}

export type WaterContextLabel =
  | "field_check_needed"
  | "watch_drainage"
  | "forecast_context_only";

/** Short, structured state of the Water card summary (localized in the UI). */
export type WaterSummaryKind =
  | "information_needed"
  | "field_check_needed"
  | "watch_drainage"
  | "monitor_conditions";

/** Machine key of one structured "what is needed next" item. */
export type NextInformationKey =
  | "growth_stage"
  | "last_irrigation_date"
  | "soil_texture"
  | "soil_moisture"
  | "drainage"
  | "weather_context";

/** One structured item of `data.next_information_needed` (never an instruction). */
export interface NextInformationItem {
  key: NextInformationKey;
  label: string;
  reason: string;
  farmer_action: string;
  priority: number;
}

/** `data` of the Water card, including the structured completeness report. */
export interface WaterCardData {
  water_attention?: string;
  water_summary_kind?: WaterSummaryKind;
  irrigation_command?: null;
  input_completeness: InputCompleteness;
  /** Machine keys of the inputs that are missing, in priority order. */
  missing_inputs: string[];
  /** Structured "what is needed next" report (labels localized in the UI). */
  next_information_needed?: NextInformationItem[];
  water_context?: {
    label?: WaterContextLabel;
    status?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

/** App-safe visible class read by the Crop agent from the Vision card. */
export type VisionFinding =
  | "absent"
  | "other"
  | "healthy_looking"
  | "rust_like_pustules"
  | "unclear";

/** Whether the uploaded photo could be screened at all. */
export type PhotoAssessmentStatus = "assessable" | "limited" | "not_assessable";

/**
 * What the photo appears to show. `wheat_leaf` is only ever claimed for a
 * frame-filling leaf close-up in leaf-screening scope; an ear/head, a
 * whole-field shot, another plant part or an unreadable subject get their own
 * code so a leaf result can never be shown for a non-leaf photo.
 */
export type PhotoSubject =
  | "wheat_leaf"
  | "wheat_ear_or_head"
  | "whole_field_or_distant_crop"
  | "other_plant_part"
  | "unclear";

/**
 * Whether the leaf-sign screening applies to this photo at all: applicable
 * only for a leaf close-up, not applicable for an ear/head or a wide view,
 * subject_unclear when the plant part could not be identified.
 */
export type ScreeningScope =
  | "leaf_screening_applicable"
  | "leaf_screening_not_applicable"
  | "subject_unclear";

/** Closed set of reportable visible-sign categories — never a disease name. */
export type VisibleSignCategory = "healthy_looking" | "rust_like_marks" | "unclear";

/** Quality gate tier of the photo that produced this report. */
export type PhotoQuality = "clear" | "limited" | "unusable";

/**
 * `data.photo_report` on the Vision card: the farmer-facing screening report.
 * Enums are codes (localized in the UI); list items and the interpretation are
 * fixed backend sentences rendered through `<BackendText>`.
 */
export interface PhotoReport {
  assessment_status: PhotoAssessmentStatus;
  photo_subject: PhotoSubject;
  /** Whether leaf-sign screening applies to this photo. */
  screening_scope: ScreeningScope;
  /** Farmer-safe reasons for the scope (never model labels or scores). */
  scope_reasons: string[];
  visible_sign_category: VisibleSignCategory;
  photo_quality: PhotoQuality;
  /** What the photo does show. */
  what_is_visible: string[];
  /** What could not be seen — or why the photo could not be read. */
  what_is_not_clearly_visible: string[];
  /** One- or two-sentence preliminary interpretation, never a diagnosis. */
  screening_interpretation: string;
  /** Farmer-answerable next checks in the field (max 3). */
  field_checks: string[];
  /** Present only when the photo must be retaken. */
  retake_guidance: string | null;
  /** Signs that mean an expert should look; empty when none apply. */
  expert_review_signs: string[];
}

/** `data` of the Crop card: the evidence split plus its screening structure. */
export interface CropCardData {
  /** Symptom tags chosen by the farmer, labelled as reports. */
  farmer_reported_symptoms?: string[];
  /** Vision observations (plus a photo limitation note when the photo is unclear). */
  photo_visible_findings?: string[];
  /** Screening possibilities only — never confirmed causes. */
  crop_possibilities?: string[];
  /** Farmer-answerable field checks, max 3, no duplicates. */
  field_checks?: string[];
  /** Signs that need expert review; empty when nothing warrants one. */
  escalation_signs?: string[];
  vision_finding?: VisionFinding;
  referral_recommended?: boolean;
  referral_reasons?: string[];
  evidence_labels?: {
    farmer_reported?: string[];
    photo_visible?: string[];
    rule_based_check?: string[];
    [key: string]: string[] | undefined;
  };
  [key: string]: unknown;
}

/* --------------------------------------------------------------- farm plan */

/** Backend `FarmCheck` (priority is constrained to 1..3). */
export interface FarmCheck {
  id: string;
  priority: 1 | 2 | 3;
  title: string;
  how_to_check: string;
  why: string;
  what_to_observe: string;
  evidence_labels: string[];
}

export type PlanStatus =
  | "insufficient_information"
  | "monitor"
  | "field_inspection_recommended"
  | "expert_review_recommended";

/** Conflicts are free-form dicts on the backend; common keys are optional. */
export interface PlanConflict {
  topic?: string;
  findings?: string[];
  next_check?: string;
  [key: string]: unknown;
}

/** Backend `FarmPlan`. */
export interface FarmPlan {
  status: PlanStatus;
  rationale: string;
  agent_summary: Record<string, string>;
  checks: FarmCheck[];
  verification_step: string;
  conflicts: PlanConflict[];
  safety_banner: string;
  policy_version: string;
  created_at: string;
}

/* --------------------------------------------------------- AI explanation */

export type AIExplanationStatus = "complete" | "skipped" | "unavailable";

export type AIExplanationReason =
  | "consent_missing"
  | "disabled"
  | "key_missing"
  | "timeout"
  | "provider_error"
  | "invalid_output";

/** Backend `AIExplanation` — the deterministic FarmPlan stays authoritative. */
export interface AIExplanation {
  status: AIExplanationStatus;
  locale: Locale;
  farmer_summary: string | null;
  evidence_explanation: string | null;
  check_explanations: string[];
  model: string | null;
  prompt_version: string;
  generated_at: string | null;
  reason: AIExplanationReason | null;
  disclaimer: string;
}

/* ---------------------------------------------------------------- results */

/**
 * `input_recap` on a stored result: exactly what the farmer entered or
 * selected, echoed back for the "Your reported field information" section.
 *
 * Every key is optional because each is present only when the intake carried
 * it — the recap can therefore never show a value nobody supplied. Unknowns
 * are the farmer's own explicit "not sure" choices, never an inferred default.
 */
export interface InputRecap {
  crop?: string;
  area_code?: string;
  growth_stage?: string;
  /** Observation date as reported (YYYY-MM-DD). */
  observed_at?: string;
  /** "known" or "not_sure" — the farmer's own selection. */
  irrigation_history?: string;
  /** Present only when irrigation_history is "known". */
  last_irrigation_date?: string;
  soil_moisture?: string;
  drainage?: string;
  symptom_onset?: string;
  symptoms_spreading?: string;
  symptoms?: string[];
  photo_count?: number;
  photo_views?: string[];
  notes_included?: boolean;
  [key: string]: unknown;
}

/** Backend `AssessmentResults` once the job has a stored result. */
export interface AssessmentResults {
  assessment_id: string;
  job_id: string;
  status: string;
  created_at: string;
  agents: AgentResult[];
  farm_plan: FarmPlan | null;
  ai_explanation: AIExplanation | null;
  input_recap: InputRecap;
  local_timezone: string;
}

/**
 * GET /results returns this placeholder until the job has a result
 * (and 404 results_not_ready when no job exists yet).
 */
export interface AssessmentResultsPending {
  assessment_id: string;
  job_id: string;
  status: string;
  agents: AgentResult[];
  farm_plan: null;
  events: JobEvent[];
}

export type AssessmentResultsResponse = AssessmentResults | AssessmentResultsPending;

/**
 * POST /assessments/{id}/analyze:
 *  - local mode → 202 body `AnalyzeAccepted` (job_id, poll /jobs/{id});
 *  - serverless mode (Vercel) → 200 body `AssessmentResults` inline.
 * Discriminate structurally: only the results carry an `agents` array.
 */
export type AnalyzeResponse = AnalyzeAccepted | AssessmentResults;

/* ------------------------------------------------------- misc API shapes */

export interface AssessmentDeleted {
  assessment_id: string;
  deleted: boolean;
  linked_images_deleted: number;
  message: string;
}

/** GET /api/v1/config (backend `public_config()`). */
export interface PublicConfig {
  product: string;
  api_version: string;
  supported_crop: string;
  supported_areas: { code: string; name: string }[];
  policy_version: string;
  source_registry_version: string;
  photo_limit_bytes: number;
  max_photos: number;
  vision_mode:
    | "private_self_hosted"
    | "local_onnx_model"
    | "quality_gate_only_no_model";
  market_mode: string;
  retention_hours: number;
  safety_notice: string;
}

/** FastAPI/HTTP error body used across the API. */
export interface ApiErrorBody {
  code: string;
  message: string;
  request_id?: string;
  details?: Record<string, unknown>;
}

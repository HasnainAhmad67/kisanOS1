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

/** Backend `AssessmentResults` once the job has a stored result. */
export interface AssessmentResults {
  assessment_id: string;
  job_id: string;
  status: string;
  created_at: string;
  agents: AgentResult[];
  farm_plan: FarmPlan | null;
  ai_explanation: AIExplanation | null;
  input_recap: Record<string, unknown>;
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

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, use_enum_values=True
    )


class GrowthStage(StrEnum):
    EMERGENCE = "emergence"
    CRI = "cri"
    TILLERING = "tillering"
    JOINTING = "jointing"
    BOOTING = "booting"
    HEADING = "heading"
    FLOWERING = "flowering"
    MILK = "milk"
    DOUGH = "dough"
    MATURITY = "maturity"
    NOT_SURE = "not_sure"


class AreaCode(StrEnum):
    BAHAWALPUR_SADAR = "bahawalpur_sadar"
    AHMADPUR_EAST = "ahmadpur_east"
    YAZMAN = "yazman"
    HASILPUR = "hasilpur"
    KHAIRPUR_TAMEWALI = "khairpur_tamewali"


class FarmerMarketQuote(StrictModel):
    market: str = Field(min_length=2, max_length=100)
    value: float = Field(gt=0, le=1_000_000)
    unit: Literal["PKR/100kg", "PKR/40kg", "PKR/tonne", "other"]
    observed_at: datetime
    note: str | None = Field(default=None, max_length=200)

    @field_validator("observed_at")
    @classmethod
    def quote_ts_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Quote timestamp must include a timezone")
        return value.astimezone(UTC)


class AssessmentCreate(StrictModel):
    crop: Literal["wheat"]
    crop_confirmed: bool
    area_code: AreaCode
    area_confirmed: bool
    growth_stage: GrowthStage = GrowthStage.NOT_SURE
    observed_at: datetime = Field(default_factory=utc_now)
    last_irrigation_date: date | None = None
    irrigation_history: Literal["known", "not_sure"] = "not_sure"
    sowing_date: date | None = None
    soil_texture: Literal["sandy", "loamy", "clayey", "not_sure"] = "not_sure"
    soil_moisture: Literal["dry", "moist", "wet", "not_sure"] = "not_sure"
    drainage: Literal["good", "poor", "waterlogging", "not_sure"] = "not_sure"
    symptom_onset: Literal["today", "recent", "over_a_week", "not_sure"] = "not_sure"
    symptoms_spreading: Literal["yes", "no", "not_sure"] = "not_sure"
    symptoms: list[str] = Field(default_factory=list, max_length=12)
    notes: str | None = Field(default=None, max_length=1500)
    locale: Literal["en", "ur", "roman_ur"] = "en"
    timezone: str = "Asia/Karachi"
    consent_given: bool
    consent_version: str = Field(min_length=1, max_length=40)
    # Separate, default-off consent for the optional external Gemini explanation.
    gemini_explanation_consent: bool = False
    gps_consent: bool = False
    latitude: float | None = Field(default=None, ge=24.0, le=38.0)
    longitude: float | None = Field(default=None, ge=60.0, le=78.0)
    market_quote: FarmerMarketQuote | None = None

    @field_validator("observed_at")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("symptoms")
    @classmethod
    def clean_symptoms(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(s[:80] for s in value if s.strip()))

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str | None) -> str | None:
        return value[:1500] if value else value

    @model_validator(mode="after")
    def intake_guardrails(self):
        if not self.crop_confirmed:
            raise ValueError("Please confirm the crop is wheat before analysis.")
        if not self.area_confirmed:
            raise ValueError("Please confirm the selected Bahawalpur pilot area.")
        if not self.consent_given:
            raise ValueError("Consent is required to save this assessment.")
        if self.latitude is not None and not self.gps_consent:
            raise ValueError("Coordinates require explicit GPS consent.")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither.")
        if self.irrigation_history == "known" and self.last_irrigation_date is None:
            raise ValueError("Provide the last irrigation date or select not_sure.")
        return self


class FollowUpCreate(StrictModel):
    note: str = Field(min_length=1, max_length=1500)
    check_ids: list[str] = Field(default_factory=list, max_length=3)
    completion: Literal[
        "completed", "not_completed", "partially_completed", "not_sure"
    ] = "not_sure"
    observed_at: datetime = Field(default_factory=utc_now)

    @field_validator("observed_at")
    @classmethod
    def followup_ts_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(UTC)


class Source(StrictModel):
    title: str
    url: str | None = None
    publisher: str
    geography: str = "Bahawalpur pilot / applicability limited"
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    source_status: Literal[
        "official",
        "supporting",
        "secondary",
        "unverified",
        "farmer_reported",
        "not_applicable",
    ]
    note: str | None = None


class AgentResult(StrictModel):
    assessment_id: str
    agent_id: Literal["weather", "water", "crop", "vision", "market"]
    status: Literal[
        "complete",
        "partial",
        "unavailable",
        "stale",
        "not_assessed",
        "unsupported",
        "error",
    ]
    summary: str
    observations: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list, max_length=8)
    evidence_band: Literal["low", "medium", "high", "not_calibrated"] = "not_calibrated"
    evidence_reason: str
    sources: list[Source] = Field(default_factory=list)
    provider_or_model: str
    version: str
    created_at: datetime = Field(default_factory=utc_now)
    safety_flags: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    input_evidence: list[str] = Field(default_factory=list)


class FarmCheck(StrictModel):
    id: str
    priority: int = Field(ge=1, le=3)
    title: str
    how_to_check: str
    why: str
    evidence_labels: list[str] = Field(default_factory=list)


class FarmPlan(StrictModel):
    status: Literal[
        "insufficient_information",
        "monitor",
        "field_inspection_recommended",
        "expert_review_recommended",
    ]
    rationale: str
    agent_summary: dict[str, str]
    checks: list[FarmCheck] = Field(max_length=3)
    verification_step: str
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    safety_banner: str
    policy_version: str
    created_at: datetime = Field(default_factory=utc_now)


class GeminiNarration(StrictModel):
    """The only narrative fields Gemini may return."""

    farmer_summary: str = Field(min_length=1, max_length=500)
    evidence_explanation: str = Field(min_length=1, max_length=800)
    check_explanations: list[str] = Field(max_length=3)


class AIExplanation(StrictModel):
    """Optional language explanation; the deterministic FarmPlan remains authoritative."""

    status: Literal["complete", "skipped", "unavailable"]
    locale: Literal["en", "ur", "roman_ur"]
    farmer_summary: str | None = Field(default=None, max_length=500)
    evidence_explanation: str | None = Field(default=None, max_length=800)
    check_explanations: list[str] = Field(default_factory=list, max_length=3)
    model: str | None = None
    prompt_version: str = "gemini-explainer-v1"
    generated_at: datetime | None = None
    reason: (
        Literal[
            "consent_missing",
            "disabled",
            "key_missing",
            "timeout",
            "provider_error",
            "invalid_output",
        ]
        | None
    ) = None
    disclaimer: str = (
        "AI-generated explanation of the Farm Advisor assessment; "
        "not a diagnosis or new agronomic advice."
    )


class AssessmentResults(StrictModel):
    assessment_id: str
    job_id: str
    status: str
    created_at: datetime
    agents: list[AgentResult]
    farm_plan: FarmPlan | None = None
    ai_explanation: AIExplanation | None = None
    input_recap: dict[str, Any]
    local_timezone: str = "Asia/Karachi"


class JobEvent(StrictModel):
    sequence: int
    phase: str
    status: Literal["started", "completed", "unavailable", "failed", "skipped"]
    timestamp: datetime = Field(default_factory=utc_now)
    detail: str | None = None


class JobStatus(StrictModel):
    job_id: str
    assessment_id: str
    state: Literal["queued", "running", "succeeded", "partial", "failed"]
    events: list[JobEvent]
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None


class AssessmentCreated(StrictModel):
    assessment_id: str
    access_token: str
    created_at: datetime
    required_photo_slots: list[str] = ["symptom_closeup", "field_context"]
    supported_areas: list[str]
    policy_version: str
    retention_hours: int
    safety_notice: str


class ErrorResponse(StrictModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)

"""
KisanOS — Crop Agent Canonical Schema
Module: agents/crop/schema.py
Adheres strictly to the KisanOS Multi-Agent Contract v2.0
Supports both Pydantic v2 and Python standard library dataclasses.
"""

from typing import List, Optional, Literal, Dict, Any
import re
from datetime import datetime
import json
import uuid

# Strict Enums matching KisanOS Contract
AgentStatus = Literal["complete", "partial", "unavailable", "error"]
EvidenceBand = Literal["low", "medium", "high", "not_calibrated"]
SourceStatus = Literal["official", "supporting", "secondary", "unverified"]
PriorityLevel = Literal["high", "medium", "low"]
CropType = Literal["wheat"]  # MVP: wheat only; future: rice, cotton, maize
GrowthStage = Literal[
    "germination", "tillering", "booting", "heading",
    "flowering", "grain_fill", "maturity", "unknown"
]
StressSeverity = Literal["low", "moderate", "high", "unknown"]

VALID_AGENT_STATUSES = {"complete", "partial", "unavailable", "error"}
VALID_EVIDENCE_BANDS = {"low", "medium", "high", "not_calibrated"}
VALID_SOURCE_STATUSES = {"official", "supporting", "secondary", "unverified"}
VALID_GROWTH_STAGES = {
    "germination", "tillering", "booting", "heading",
    "flowering", "grain_fill", "maturity", "unknown"
}

# Prohibited Agronomic / Chemical Keywords (Violation = Rejection)
PROHIBITED_CHEMICAL_KEYWORDS = [
    "urea", "dap", "npk", "fertilizer", "pesticide", "fungicide", "herbicide",
    "insecticide", "spray", "paraquat", "chlorpyrifos", "glyphosate",
    "imidacloprid", "mancozeb", "deltamethrin", "emamectin", "dose", "dosage",
    "kg/acre", "ml/acre", "liters/acre", "gm/acre", "irrigate now", "turn on pump",
    "weedicide", "weed killer", "rust spray", "aphid spray", "chemical treatment"
]


def _check_safety_text(texts: List[str]):
    """Strict safety gate: reject any output mentioning chemicals, doses, or irrigation commands."""
    for text in texts:
        lower_text = str(text).lower()
        for keyword in PROHIBITED_CHEMICAL_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, lower_text):
                raise ValueError(
                    f"Safety Violation: Prohibited chemical/prescription keyword '{keyword}' found in crop agent output."
                )


def _validate_iso_ts(ts: str) -> str:
    try:
        clean_ts = ts.replace("Z", "+00:00")
        datetime.fromisoformat(clean_ts)
    except Exception:
        raise ValueError(f"Invalid ISO-8601 timestamp: {ts}")
    return ts


def _validate_uuid(val: Any) -> str:
    if not isinstance(val, str) or not val.strip():
        raise ValueError(f"Invalid assessment_id: must be a non-empty valid UUID string, got {val!r}")
    cleaned = val.strip()
    try:
        parsed = uuid.UUID(cleaned)
        if str(parsed) != cleaned.lower():
            raise ValueError(f"assessment_id '{val}' does not conform to canonical RFC-4122 format")
    except Exception as e:
        raise ValueError(f"Invalid assessment_id '{val}': Must be a valid RFC-4122 UUID. Details: {e}")
    return cleaned


try:
    from pydantic import BaseModel, Field, field_validator

    class SourceRecord(BaseModel):
        title: str = Field(..., description="Source name")
        url: str = Field(..., description="Source URL or API reference")
        publisher: str = Field(..., description="Publisher name (e.g., PARC, Punjab Agri Dept)")
        retrieved_at: str = Field(..., description="ISO-8601 timestamp")
        source_status: SourceStatus = Field(..., description="Verification tier of the source")

        @field_validator("retrieved_at")
        @classmethod
        def validate_retrieved_at(cls, v: str) -> str:
            return _validate_iso_ts(v)

        @field_validator("source_status")
        @classmethod
        def validate_source_status(cls, v: str) -> str:
            if v not in VALID_SOURCE_STATUSES:
                raise ValueError(f"Invalid source_status '{v}'. Must be one of: {sorted(VALID_SOURCE_STATUSES)}")
            return v

    class AIEnhanced(BaseModel):
        urdu_summary: str
        roman_urdu: str
        audio_script_urdu: str
        emoji_visual: str
        farmer_explanation: str
        priority_level: PriorityLevel

    class CropDetails(BaseModel):
        crop_type: str = "wheat"
        growth_stage: GrowthStage = "unknown"
        days_since_sowing: Optional[int] = None
        days_since_irrigation: Optional[int] = None
        sowing_date: Optional[str] = None
        reported_symptoms: List[str] = Field(default_factory=list)
        stress_indicators: List[str] = Field(default_factory=list)
        stress_severity: StressSeverity = "unknown"
        recommended_checks_count: int = 0
        next_stage_expected_days: Optional[int] = None

    class CropAgentResponse(BaseModel):
        agent_id: Literal["crop"] = "crop"
        assessment_id: str
        status: AgentStatus
        summary: str
        observations: List[str]
        possible_causes: List[str]
        checks: List[str]
        evidence_band: EvidenceBand
        evidence_reason: str
        sources: List[SourceRecord]
        provider_or_model: str
        version: str = "1.0"
        created_at: str
        safety_flags: List[str] = Field(default_factory=list)
        AI_ENHANCED: Optional[AIEnhanced] = None
        crop_details: Optional[CropDetails] = None

        @field_validator("assessment_id")
        @classmethod
        def validate_assessment_uuid(cls, v: str) -> str:
            return _validate_uuid(v)

        @field_validator("status")
        @classmethod
        def validate_status(cls, v: str) -> str:
            if v not in VALID_AGENT_STATUSES:
                raise ValueError(f"Invalid status '{v}'. Must be one of: {sorted(VALID_AGENT_STATUSES)}")
            return v

        @field_validator("evidence_band")
        @classmethod
        def validate_evidence_band(cls, v: str) -> str:
            if v not in VALID_EVIDENCE_BANDS:
                raise ValueError(f"Invalid evidence_band '{v}'. Must be one of: {sorted(VALID_EVIDENCE_BANDS)}")
            return v

        @field_validator("created_at")
        @classmethod
        def validate_created_at(cls, v: str) -> str:
            return _validate_iso_ts(v)

        @field_validator("summary", "observations", "checks", "possible_causes")
        @classmethod
        def validate_safety(cls, v: Any) -> Any:
            if isinstance(v, str):
                _check_safety_text([v])
            elif isinstance(v, list):
                _check_safety_text([str(x) for x in v])
            return v

except ImportError:
    # Standard library fallback if pydantic is not installed
    class SourceRecord:
        def __init__(self, title: str, url: str, publisher: str, retrieved_at: str, source_status: str):
            if source_status not in VALID_SOURCE_STATUSES:
                raise ValueError(f"Invalid source_status '{source_status}'. Must be one of: {sorted(VALID_SOURCE_STATUSES)}")
            self.title = title
            self.url = url
            self.publisher = publisher
            self.retrieved_at = _validate_iso_ts(retrieved_at)
            self.source_status = source_status

        def model_dump(self) -> Dict[str, Any]:
            return {
                "title": self.title, "url": self.url, "publisher": self.publisher,
                "retrieved_at": self.retrieved_at, "source_status": self.source_status,
            }

    class CropDetails:
        def __init__(self, **kwargs):
            self.crop_type = kwargs.get("crop_type", "wheat")
            self.growth_stage = kwargs.get("growth_stage", "unknown")
            self.days_since_sowing = kwargs.get("days_since_sowing")
            self.days_since_irrigation = kwargs.get("days_since_irrigation")
            self.sowing_date = kwargs.get("sowing_date")
            self.reported_symptoms = kwargs.get("reported_symptoms", [])
            self.stress_indicators = kwargs.get("stress_indicators", [])
            self.stress_severity = kwargs.get("stress_severity", "unknown")
            self.recommended_checks_count = kwargs.get("recommended_checks_count", 0)
            self.next_stage_expected_days = kwargs.get("next_stage_expected_days")

        def model_dump(self) -> Dict[str, Any]:
            return dict(self.__dict__)

    class CropAgentResponse:
        def __init__(self, **kwargs):
            required_keys = [
                "assessment_id", "status", "summary", "observations",
                "possible_causes", "checks", "evidence_band", "evidence_reason",
                "sources", "provider_or_model", "created_at",
            ]
            for key in required_keys:
                if key not in kwargs or kwargs[key] is None:
                    raise ValueError(f"Missing mandatory field '{key}'")

            self.agent_id = "crop"
            self.assessment_id = _validate_uuid(kwargs["assessment_id"])

            if kwargs["status"] not in VALID_AGENT_STATUSES:
                raise ValueError(f"Invalid status '{kwargs['status']}'")
            self.status = kwargs["status"]

            if kwargs["evidence_band"] not in VALID_EVIDENCE_BANDS:
                raise ValueError(f"Invalid evidence_band '{kwargs['evidence_band']}'")
            self.evidence_band = kwargs["evidence_band"]

            self.summary = kwargs["summary"]
            self.observations = kwargs["observations"]
            self.possible_causes = kwargs["possible_causes"]
            self.checks = kwargs["checks"]
            self.evidence_reason = kwargs["evidence_reason"]
            self.sources = kwargs["sources"]
            self.provider_or_model = kwargs["provider_or_model"]
            self.version = kwargs.get("version", "1.0")
            self.created_at = _validate_iso_ts(kwargs["created_at"])
            self.safety_flags = kwargs.get("safety_flags", [])
            self.AI_ENHANCED = kwargs.get("AI_ENHANCED")
            self.crop_details = kwargs.get("crop_details")

            _check_safety_text([self.summary] + self.observations + self.possible_causes + self.checks)

        def model_dump(self) -> Dict[str, Any]:
            res = {
                "agent_id": self.agent_id,
                "assessment_id": self.assessment_id,
                "status": self.status,
                "summary": self.summary,
                "observations": self.observations,
                "possible_causes": self.possible_causes,
                "checks": self.checks,
                "evidence_band": self.evidence_band,
                "evidence_reason": self.evidence_reason,
                "sources": [s.model_dump() if hasattr(s, "model_dump") else s for s in self.sources],
                "provider_or_model": self.provider_or_model,
                "version": self.version,
                "created_at": self.created_at,
                "safety_flags": self.safety_flags,
            }
            if self.AI_ENHANCED:
                res["AI_ENHANCED"] = self.AI_ENHANCED
            if self.crop_details:
                res["crop_details"] = (
                    self.crop_details.model_dump()
                    if hasattr(self.crop_details, "model_dump")
                    else self.crop_details
                )
            return res


def validate_crop_payload(payload: Dict[str, Any]) -> CropAgentResponse:
    return CropAgentResponse(**payload)
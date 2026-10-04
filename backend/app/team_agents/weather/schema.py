"""
KisanOS — Weather Agent Canonical Schema
Module: agents/weather/schema.py
Adheres strictly to the KisanOS Multi-Agent Contract v2.0
Supports both Pydantic v2 and Python standard library dataclasses.
"""

from typing import List, Optional, Literal, Dict, Any
import re
from datetime import datetime
import json

# Strict Enums matching KisanOS Contract
AgentStatus = Literal["complete", "partial", "unavailable", "error"]
EvidenceBand = Literal["low", "medium", "high", "not_calibrated"]
SourceStatus = Literal["official", "supporting", "secondary", "unverified"]
PriorityLevel = Literal["high", "medium", "low"]

# Prohibited Agronomic / Chemical Keywords (Violation = Rejection)
PROHIBITED_CHEMICAL_KEYWORDS = [
    "urea", "dap", "npk", "fertilizer", "pesticide", "fungicide", "herbicide",
    "insecticide", "spray", "paraquat", "chlorpyrifos", "glyphosate",
    "imidacloprid", "mancozeb", "deltamethrin", "emamectin", "dose", "dosage",
    "kg/acre", "ml/acre", "liters/acre", "gm/acre", "irrigate now", "turn on pump"
]

def _check_safety_text(texts: List[str]):
    for text in texts:
        lower_text = text.lower()
        for keyword in PROHIBITED_CHEMICAL_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, lower_text):
                raise ValueError(
                    f"Safety Violation: Prohibited chemical/prescription keyword '{keyword}' found in weather agent output."
                )

def _validate_iso_ts(ts: str) -> str:
    try:
        clean_ts = ts.replace("Z", "+00:00")
        datetime.fromisoformat(clean_ts)
    except Exception:
        raise ValueError(f"Invalid ISO-8601 timestamp: {ts}")
    return ts


try:
    from pydantic import BaseModel, Field, field_validator

    class SourceRecord(BaseModel):
        title: str = Field(..., description="Source name")
        url: str = Field(..., description="Source URL or API reference")
        publisher: str = Field(..., description="Publisher name (e.g., Open-Meteo, PMD)")
        retrieved_at: str = Field(..., description="ISO-8601 timestamp")
        source_status: SourceStatus = Field(..., description="Verification tier of the source")

        @field_validator("retrieved_at")
        @classmethod
        def validate_retrieved_at(cls, v: str) -> str:
            return _validate_iso_ts(v)

    class AIEnhanced(BaseModel):
        urdu_summary: str
        roman_urdu: str
        audio_script_urdu: str
        emoji_visual: str
        farmer_explanation: str
        priority_level: PriorityLevel

    class DailyForecastItem(BaseModel):
        date: str
        temp_max: float
        temp_min: float
        precipitation_sum_mm: float
        precipitation_prob_max: int
        weather_condition: str
        wind_speed_max_kmh: float

    class WeatherDetails(BaseModel):
        location_name: str
        tehsil: str
        district: str = "Bahawalpur"
        province: str = "Punjab"
        latitude: float
        longitude: float
        elevation_m: Optional[float] = None
        timezone: str = "Asia/Karachi"
        temperature_c: float
        apparent_temp_c: float
        relative_humidity_pct: int
        wind_speed_kmh: float
        weather_description: str
        rain_probability_pct: int
        historical_temp_anomaly_c: float
        heat_stress_risk: str
        rust_favorable_condition: str
        daily_7day_outlook: List[DailyForecastItem] = Field(default_factory=list)

    class WeatherAgentResponse(BaseModel):
        agent_id: Literal["weather"] = "weather"
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
        weather_details: Optional[WeatherDetails] = None

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
            self.title = title
            self.url = url
            self.publisher = publisher
            self.retrieved_at = _validate_iso_ts(retrieved_at)
            self.source_status = source_status

        def model_dump(self) -> Dict[str, Any]:
            return {
                "title": self.title,
                "url": self.url,
                "publisher": self.publisher,
                "retrieved_at": self.retrieved_at,
                "source_status": self.source_status
            }

    class DailyForecastItem:
        def __init__(self, date: str, temp_max: float, temp_min: float, precipitation_sum_mm: float,
                     precipitation_prob_max: int, weather_condition: str, wind_speed_max_kmh: float):
            self.date = date
            self.temp_max = temp_max
            self.temp_min = temp_min
            self.precipitation_sum_mm = precipitation_sum_mm
            self.precipitation_prob_max = precipitation_prob_max
            self.weather_condition = weather_condition
            self.wind_speed_max_kmh = wind_speed_max_kmh

        def model_dump(self) -> Dict[str, Any]:
            return self.__dict__

    class WeatherDetails:
        def __init__(self, location_name: str, tehsil: str, latitude: float, longitude: float,
                     temperature_c: float, apparent_temp_c: float, relative_humidity_pct: int,
                     wind_speed_kmh: float, weather_description: str, rain_probability_pct: int,
                     historical_temp_anomaly_c: float, heat_stress_risk: str, rust_favorable_condition: str,
                     district: str = "Bahawalpur", province: str = "Punjab", elevation_m: Optional[float] = None,
                     timezone: str = "Asia/Karachi", daily_7day_outlook: Optional[List[DailyForecastItem]] = None):
            self.location_name = location_name
            self.tehsil = tehsil
            self.district = district
            self.province = province
            self.latitude = latitude
            self.longitude = longitude
            self.elevation_m = elevation_m
            self.timezone = timezone
            self.temperature_c = temperature_c
            self.apparent_temp_c = apparent_temp_c
            self.relative_humidity_pct = relative_humidity_pct
            self.wind_speed_kmh = wind_speed_kmh
            self.weather_description = weather_description
            self.rain_probability_pct = rain_probability_pct
            self.historical_temp_anomaly_c = historical_temp_anomaly_c
            self.heat_stress_risk = heat_stress_risk
            self.rust_favorable_condition = rust_favorable_condition
            self.daily_7day_outlook = daily_7day_outlook or []

        def model_dump(self) -> Dict[str, Any]:
            d = dict(self.__dict__)
            d["daily_7day_outlook"] = [i.model_dump() if hasattr(i, "model_dump") else i for i in self.daily_7day_outlook]
            return d

    class WeatherAgentResponse:
        def __init__(self, **kwargs):
            self.agent_id = "weather"
            self.assessment_id = kwargs["assessment_id"]
            self.status = kwargs["status"]
            self.summary = kwargs["summary"]
            self.observations = kwargs["observations"]
            self.possible_causes = kwargs["possible_causes"]
            self.checks = kwargs["checks"]
            self.evidence_band = kwargs["evidence_band"]
            self.evidence_reason = kwargs["evidence_reason"]
            self.sources = kwargs["sources"]
            self.provider_or_model = kwargs["provider_or_model"]
            self.version = kwargs.get("version", "1.0")
            self.created_at = _validate_iso_ts(kwargs["created_at"])
            self.safety_flags = kwargs.get("safety_flags", [])
            self.AI_ENHANCED = kwargs.get("AI_ENHANCED")
            self.weather_details = kwargs.get("weather_details")

            # Validate safety
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
                "safety_flags": self.safety_flags
            }
            if self.AI_ENHANCED:
                res["AI_ENHANCED"] = self.AI_ENHANCED
            if self.weather_details:
                res["weather_details"] = self.weather_details.model_dump() if hasattr(self.weather_details, "model_dump") else self.weather_details
            return res


def validate_weather_payload(payload: Dict[str, Any]) -> WeatherAgentResponse:
    return WeatherAgentResponse(**payload)

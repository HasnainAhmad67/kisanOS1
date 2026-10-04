from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


Status = Literal["complete", "partial", "stale", "unavailable", "error"]
Freshness = Literal["fresh", "stale", "unavailable"]
Locale = Literal["en", "ur", "roman_ur"]


class SourceRecord(StrictModel):
    title: str
    url: str
    publisher: str
    retrieved_at: str | None = None
    source_status: Literal["official", "supporting", "secondary", "unverified"]
    note: str | None = None


class CurrentWeather(StrictModel):
    time: str | None = None
    temperature_c: float | None = None
    relative_humidity_pct: int | None = Field(default=None, ge=0, le=100)
    precipitation_mm_previous_hour: float | None = Field(default=None, ge=0)
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    wind_direction_deg: int | None = Field(default=None, ge=0, le=360)
    rainfall_mm: float | None = Field(default=None, ge=0)
    rainfall_24h_mm: float | None = Field(default=None, ge=0)
    wind_direction: str | None = None
    dew_point_c: float | None = None
    pressure_hpa: float | None = Field(default=None, ge=0)
    visibility_km: float | None = Field(default=None, ge=0)
    station: str | None = None
    source_time: str | None = None
    weather_code: int | None = None
    description: str


class HourlyForecast(StrictModel):
    time: str
    temperature_c: float | None = None
    relative_humidity_pct: int | None = Field(default=None, ge=0, le=100)
    precipitation_probability_pct: int | None = Field(default=None, ge=0, le=100)
    precipitation_mm: float | None = Field(default=None, ge=0)
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    wind_direction_deg: int | None = Field(default=None, ge=0, le=360)
    weather_code: int | None = None


class DailyForecast(StrictModel):
    date: str
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    precipitation_sum_mm: float | None = Field(default=None, ge=0)
    precipitation_probability_max_pct: int | None = Field(default=None, ge=0, le=100)
    wind_speed_max_kmh: float | None = Field(default=None, ge=0)
    weather_code: int | None = None
    description: str


class WeatherDetails(StrictModel):
    location_name: str
    district: str = "Bahawalpur"
    province: str = "Punjab"
    location_granularity: Literal[
        "tehsil_forecast_grid", "consented_coordinate_forecast_grid"
    ]
    forecast_grid_latitude: float | None = None
    forecast_grid_longitude: float | None = None
    timezone: str
    provider: str = "PMD FFD + Open-Meteo"
    provider_current_time: str | None = None
    provider_model_run_time: str | None = None
    provider_model_run_time_note: str = (
        "The API response does not expose a verified model-run timestamp."
    )
    retrieved_at: str | None = None
    units: dict[str, str]
    freshness: Freshness
    cache_status: Literal["live", "stale", "unavailable"]
    cache_age_seconds: int | None = Field(default=None, ge=0)
    current: CurrentWeather | None = None
    hourly_next_72h: list[HourlyForecast] = Field(default_factory=list, max_length=72)
    daily_outlook_7d: list[DailyForecast] = Field(default_factory=list, max_length=7)
    weather_watch_signals: list[dict[str, Any]] = Field(default_factory=list)
    # Provider panels keep their own provenance, location resolution, units and freshness.
    providers: dict[str, Any] = Field(default_factory=dict)


class AIEnhanced(StrictModel):
    urdu_summary: str
    roman_urdu: str
    audio_script_urdu: str
    emoji_visual: str
    farmer_explanation: str
    priority_level: Literal["low", "medium", "high"] = "low"
    mode: Literal["deterministic_translation"] = "deterministic_translation"


class WeatherAgentResponse(StrictModel):
    agent_id: Literal["weather"] = "weather"
    assessment_id: str
    status: Status
    summary: str
    observations: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    evidence_band: Literal["low", "medium", "high", "not_calibrated"]
    evidence_reason: str
    sources: list[SourceRecord] = Field(default_factory=list)
    provider_or_model: str = "open-meteo"
    version: str = "2.0.0"
    created_at: str
    safety_flags: list[str] = Field(default_factory=list)
    AI_ENHANCED: AIEnhanced | None = None
    weather_details: WeatherDetails | None = None


def validate_weather_payload(payload: dict[str, Any]) -> WeatherAgentResponse:
    return WeatherAgentResponse.model_validate(payload)

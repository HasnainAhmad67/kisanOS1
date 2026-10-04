from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "KisanOS API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/kisanos.db"
    image_storage_dir: Path = Path("./data/images")
    image_retention_hours: int = Field(default=24, ge=1, le=720)
    max_upload_bytes: int = Field(
        default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024
    )
    max_images_per_assessment: int = Field(default=4, ge=1, le=8)
    agent_timeout_seconds: float = Field(default=15.0, ge=1, le=120)
    weather_timeout_seconds: float = Field(default=8.0, ge=1, le=30)
    pmd_weather_current_url: str = "https://ffd.pmd.gov.pk/weather/current"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_cache_path: Path = Path("./data/weather_cache.sqlite3")
    pmd_min_refresh_seconds: int = Field(default=600, ge=600, le=86_400)
    open_meteo_min_refresh_seconds: int = Field(default=3600, ge=900, le=86_400)
    weather_current_max_cache_age_seconds: int = Field(
        default=21_600, ge=600, le=21_600
    )
    weather_forecast_max_cache_age_seconds: int = Field(
        default=86_400, ge=3600, le=172_800
    )
    vision_inference_url: str | None = None
    vision_inference_token: str | None = None
    market_adapter_url: str | None = None
    allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    demo_mode: bool = True
    source_registry_version: str = "2026-10-03.1"
    policy_version: str = "kisanos-safe-policy-1.0.0"
    consent_version: str = "2026-10-03-gemini-v1"
    log_level: str = "INFO"

    # Optional farmer-language explanation layer. Disabled unless explicitly enabled.
    gemini_enabled: bool = False
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: float = Field(default=10.0, ge=1, le=30)

    @property
    def origins(self) -> list[str]:
        return [v.strip() for v in self.allow_origins.split(",") if v.strip()]


# Pilot areas are an explicit allowlist, not a geocoder or automatic fallback.
AREAS: dict[str, dict[str, float | str]] = {
    "bahawalpur_sadar": {"name": "Bahawalpur Sadar", "lat": 29.3956, "lon": 71.6836},
    "ahmadpur_east": {"name": "Ahmadpur East", "lat": 29.1431, "lon": 71.2599},
    "yazman": {"name": "Yazman", "lat": 29.1211, "lon": 71.7456},
    "hasilpur": {"name": "Hasilpur", "lat": 29.6967, "lon": 72.5542},
    "khairpur_tamewali": {"name": "Khairpur Tamewali", "lat": 29.5806, "lon": 72.2478},
}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.image_storage_dir.mkdir(parents=True, exist_ok=True)
    return settings

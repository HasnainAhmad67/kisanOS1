from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .cache import WeatherCache

VERSION = "3.0.0"
PMD_CURRENT_URL = "https://ffd.pmd.gov.pk/weather/current"
PMD_WIDGET_URL = "https://ffd.pmd.gov.pk/weather-widget"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
LOCAL_TIMEZONE = "Asia/Karachi"
MAX_RESPONSE_BYTES = 1_000_000
PMD_REFRESH_SECONDS = 600  # The official PMD widget says its display refreshes every 10 minutes.
OPEN_METEO_REFRESH_SECONDS = 3600
CURRENT_MAX_AGE_SECONDS = 6 * 60 * 60
FORECAST_MAX_STALE_SECONDS = 24 * 60 * 60


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON numeric literal: {value}")


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


class WeatherProviderError(RuntimeError):
    """Provider unavailable, malformed, or beyond the allowed stale-data window."""


class WeatherProviderClient:
    """Bounded, source-aware clients for the two PRD-approved weather products.

    PMD owns the current station observation and the documented 12-hour interpolated
    forecast. Open-Meteo is used only for the next 72 hours and seven daily outlook rows.
    Each provider has its own cache key, retrieval timestamp, source hash and stale status.
    """

    def __init__(
        self,
        cache: WeatherCache,
        *,
        pmd_current_url: str = PMD_CURRENT_URL,
        open_meteo_url: str = OPEN_METEO_FORECAST_URL,
        timeout_seconds: float = 3.5,
        retries: int = 1,
        pmd_refresh_seconds: int = PMD_REFRESH_SECONDS,
        open_meteo_refresh_seconds: int = OPEN_METEO_REFRESH_SECONDS,
        current_max_age_seconds: int = CURRENT_MAX_AGE_SECONDS,
        forecast_max_stale_seconds: int = FORECAST_MAX_STALE_SECONDS,
    ) -> None:
        pmd = urllib.parse.urlsplit(pmd_current_url)
        if pmd.scheme != "https" or pmd.hostname != "ffd.pmd.gov.pk" or not pmd.path.endswith("/weather/current"):
            raise ValueError("PMD URL must be the documented HTTPS FFD weather/current endpoint")
        meteo = urllib.parse.urlsplit(open_meteo_url)
        if meteo.scheme not in {"https", "http"} or not meteo.netloc:
            raise ValueError("OPEN_METEO_URL must be an HTTP(S) endpoint")
        if not 0 < timeout_seconds <= 30 or not 0 <= retries <= 4:
            raise ValueError("Invalid weather provider timeout or retry count")
        self.cache = cache
        self.pmd_current_url = pmd_current_url
        self.open_meteo_url = open_meteo_url
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.pmd_refresh_seconds = max(PMD_REFRESH_SECONDS, int(pmd_refresh_seconds))
        self.open_meteo_refresh_seconds = max(900, int(open_meteo_refresh_seconds))
        self.current_max_age_seconds = min(CURRENT_MAX_AGE_SECONDS, int(current_max_age_seconds))
        self.forecast_max_stale_seconds = max(3600, int(forecast_max_stale_seconds))

    @staticmethod
    def _age_seconds(fetched_at: datetime, now: datetime) -> int:
        return max(0, int((now - fetched_at.astimezone(UTC)).total_seconds()))

    @staticmethod
    def _cache_safe_open_meteo(payload: dict[str, Any]) -> dict[str, Any]:
        # Provider grid coordinates are not needed to reuse the cached forecast. The key
        # uses a coarse hashed cell; do not persist any coordinate fields in the payload.
        return {key: value for key, value in payload.items() if key not in {"latitude", "longitude"}}

    def _request_json(self, url: str, params: dict[str, str], *, expected_host: str | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        full_url = f"{url}{'&' if '?' in url else '?'}{query}"
        request = urllib.request.Request(
            full_url,
            headers={
                "Accept": "application/json",
                "User-Agent": f"KisanOS-WeatherAgent/{VERSION}",
            },
            method="GET",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    final_url = getattr(response, "geturl", lambda: full_url)()
                    if expected_host and urllib.parse.urlsplit(final_url).hostname != expected_host:
                        raise ValueError("Weather provider redirected outside its documented host")
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("Weather provider response exceeded the 1 MB limit")
                decoded = json.loads(
                    body.decode("utf-8"),
                    parse_constant=_reject_nonstandard_json_constant,
                )
                if not isinstance(decoded, dict):
                    raise TypeError("Weather provider response must be a JSON object")
                return decoded
            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                TypeError,
                ValueError,
            ) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(0.2 * (2**attempt), 0.6))
        raise WeatherProviderError(f"Weather provider request failed ({type(last_error).__name__})") from last_error

    def _request_pmd(self, latitude: float, longitude: float) -> dict[str, Any]:
        # PMD explicitly documents `lat` and `lng`; for confirmed area centroids these are
        # coarse town inputs, and for exact farmer GPS they are sent only after consent.
        return self._request_json(
            self.pmd_current_url,
            {"lat": f"{latitude:.6f}", "lng": f"{longitude:.6f}"},
            expected_host="ffd.pmd.gov.pk",
        )

    def _request_open_meteo_outlook(self, latitude: float, longitude: float) -> dict[str, Any]:
        params = {
            "latitude": f"{latitude:.6f}",
            "longitude": f"{longitude:.6f}",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,weather_code",
            "forecast_days": "7",
            "forecast_hours": "72",
            "timezone": LOCAL_TIMEZONE,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }
        return self._request_json(self.open_meteo_url, params)

    @staticmethod
    def valid_pmd_payload(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        city = payload.get("city")
        forecast = payload.get("forecast")
        if not isinstance(city, dict) or not isinstance(forecast, dict):
            return False
        if not all(isinstance(city.get(field), str) and city[field] for field in ("slug", "name", "province")):
            return False
        try:
            city_lat = float(city.get("lat"))
            city_lon = float(city.get("lng"))
        except (TypeError, ValueError):
            return False
        if not (-90 <= city_lat <= 90 and -180 <= city_lon <= 180):
            return False
        observed_at = payload.get("observed_at")
        if not isinstance(observed_at, str):
            return False
        observed = _parse_iso_timestamp(observed_at)
        if observed is None:
            return False
        if observed.tzinfo is None:
            return False
        if not any(
            WeatherProviderClient._number(payload.get(field), low, high) is not None
            for field, low, high in (
                ("temperature", -80, 65),
                ("humidity_pct", 0, 100),
                ("rainfall_mm", 0, 5000),
                ("rainfall_24h_mm", 0, 5000),
                ("wind_kmh", 0, 500),
            )
        ):
            return False
        hours = forecast.get("hours")
        if not isinstance(hours, list) or len(hours) != 12:
            return False
        previous: datetime | None = None
        for row in hours:
            if not isinstance(row, dict) or not isinstance(row.get("at"), str):
                return False
            timestamp = _parse_iso_timestamp(row["at"])
            if timestamp is None:
                return False
            if timestamp.tzinfo is None or (previous is not None and timestamp <= previous):
                return False
            previous = timestamp
            if row.get("temp") is not None and WeatherProviderClient._number(row.get("temp"), -80, 65) is None:
                return False
            if row.get("rain_mm") is not None and WeatherProviderClient._number(row.get("rain_mm"), 0, 1000) is None:
                return False
        return payload.get("is_live") is None or isinstance(payload.get("is_live"), bool)

    @staticmethod
    def valid_open_meteo_outlook(payload: Any) -> bool:
        if not isinstance(payload, dict) or not isinstance(payload.get("timezone"), str):
            return False
        try:
            zone = ZoneInfo(payload["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            return False
        hourly = payload.get("hourly")
        daily = payload.get("daily")
        if not isinstance(hourly, dict) or not isinstance(daily, dict):
            return False
        hours = hourly.get("time")
        days = daily.get("time")
        if not isinstance(hours, list) or len(hours) < 72 or not isinstance(days, list) or len(days) < 7:
            return False
        parsed_hours = [_parse_iso_timestamp(value) for value in hours[:72]]
        if any(value is None for value in parsed_hours):
            return False
        normalized_hours = [
            value.replace(tzinfo=zone) if value.tzinfo is None else value.astimezone(UTC) for value in parsed_hours
        ]
        if any(normalized_hours[index] >= normalized_hours[index + 1] for index in range(71)):
            return False
        try:
            parsed_days = [datetime.fromisoformat(value[:10]).date() for value in days[:7] if isinstance(value, str)]
        except ValueError:
            return False
        if len(parsed_days) != 7 or any(parsed_days[index] >= parsed_days[index + 1] for index in range(6)):
            return False
        for field in (
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation_probability",
            "precipitation",
            "wind_speed_10m",
            "wind_direction_10m",
            "weather_code",
        ):
            values = hourly.get(field)
            if not isinstance(values, list) or len(values) < 72:
                return False
            bounds = {
                "temperature_2m": (-80, 65),
                "relative_humidity_2m": (0, 100),
                "precipitation_probability": (0, 100),
                "precipitation": (0, 2000),
                "wind_speed_10m": (0, 500),
                "wind_direction_10m": (0, 360),
                "weather_code": (0, 1000),
            }[field]
            if any(
                value is not None and WeatherProviderClient._number(value, *bounds) is None for value in values[:72]
            ):
                return False
        for field in (
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "weather_code",
        ):
            values = daily.get(field)
            if not isinstance(values, list) or len(values) < 7:
                return False
            bounds = {
                "temperature_2m_max": (-80, 65),
                "temperature_2m_min": (-80, 65),
                "precipitation_sum": (0, 30_000),
                "precipitation_probability_max": (0, 100),
                "wind_speed_10m_max": (0, 500),
                "weather_code": (0, 1000),
            }[field]
            if any(value is not None and WeatherProviderClient._number(value, *bounds) is None for value in values[:7]):
                return False
        return True

    @staticmethod
    def _number(value: Any, minimum: float, maximum: float) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and minimum <= number <= maximum else None

    @staticmethod
    def _decorate(
        payload: dict[str, Any],
        *,
        provider: str,
        cache_status: str,
        fetched_at: datetime,
        age_seconds: int,
    ) -> dict[str, Any]:
        preserved_hash = payload.get("_kisanos_source_snapshot_sha256")
        snapshot = (
            preserved_hash
            if isinstance(preserved_hash, str)
            else hashlib.sha256(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
        )
        now = datetime.now(UTC)
        result = {key: value for key, value in payload.items() if key != "_kisanos_source_snapshot_sha256"}
        result["_kisanos_weather"] = {
            "provider": provider,
            "cache_status": cache_status,
            "source_fetch_at": fetched_at.astimezone(UTC).isoformat(),
            "served_at": now.isoformat(),
            "cache_age_seconds": age_seconds,
            "snapshot_sha256": snapshot,
        }
        return result

    def _fetch_cached(
        self,
        *,
        provider: str,
        latitude: float,
        longitude: float,
        endpoint_key: str,
        request: Callable[[], dict[str, Any]],
        validate: Callable[[Any], bool],
        min_refresh_seconds: int,
        max_stale_seconds: int,
        strip_coordinates: bool = False,
    ) -> dict[str, Any]:
        key = WeatherCache.key(latitude, longitude, endpoint_key)
        now = datetime.now(UTC)
        cached = self.cache.get(key)
        if cached is not None:
            cached_payload, cached_at = cached
            age = self._age_seconds(cached_at, now)
            if age <= min_refresh_seconds and validate(cached_payload):
                return self._decorate(
                    cached_payload,
                    provider=provider,
                    cache_status="fresh_cache",
                    fetched_at=cached_at,
                    age_seconds=age,
                )
        else:
            cached_payload, cached_at, age = {}, now, 0

        try:
            payload = request()
            if not validate(payload):
                raise ValueError("Weather response failed provider-specific validation")
            fetched_at = datetime.now(UTC)
            safe_payload = self._cache_safe_open_meteo(payload) if strip_coordinates else payload
            if strip_coordinates:
                safe_payload["_kisanos_source_snapshot_sha256"] = hashlib.sha256(
                    json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest()
            try:
                self.cache.put(key, safe_payload, fetched_at)
            except (OSError, ValueError, sqlite3.Error):
                # A disk-cache outage must not discard a validated live provider response.
                pass
            return self._decorate(
                payload,
                provider=provider,
                cache_status="live",
                fetched_at=fetched_at,
                age_seconds=0,
            )
        except (
            RuntimeError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            if cached and age <= max_stale_seconds and validate(cached_payload):
                return self._decorate(
                    cached_payload,
                    provider=provider,
                    cache_status="stale",
                    fetched_at=cached_at,
                    age_seconds=age,
                )
            raise WeatherProviderError(f"{provider} has no usable response or cache") from exc

    def fetch_pmd_current(
        self,
        latitude: float,
        longitude: float,
        *,
        request: Callable[[float, float], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._fetch_cached(
            provider="pmd_ffd",
            latitude=latitude,
            longitude=longitude,
            endpoint_key=self.pmd_current_url,
            request=lambda: (request or self._request_pmd)(latitude, longitude),
            validate=self.valid_pmd_payload,
            min_refresh_seconds=self.pmd_refresh_seconds,
            max_stale_seconds=self.current_max_age_seconds,
        )

    def fetch_open_meteo_outlook(self, latitude: float, longitude: float) -> dict[str, Any]:
        return self._fetch_cached(
            provider="open-meteo",
            latitude=latitude,
            longitude=longitude,
            endpoint_key=f"{self.open_meteo_url}|forecast-72h-7d",
            request=lambda: self._request_open_meteo_outlook(latitude, longitude),
            validate=self.valid_open_meteo_outlook,
            min_refresh_seconds=self.open_meteo_refresh_seconds,
            max_stale_seconds=self.forecast_max_stale_seconds,
            strip_coordinates=True,
        )

    def fetch_open_meteo_current_bundle(
        self,
        latitude: float,
        longitude: float,
        request: Callable[[float, float], dict[str, Any]],
        validate: Callable[[Any], bool],
    ) -> dict[str, Any]:
        """Compatibility method for existing callers; current data are still max-age gated."""
        return self._fetch_cached(
            provider="open-meteo",
            latitude=latitude,
            longitude=longitude,
            endpoint_key=f"{self.open_meteo_url}|legacy-current-bundle",
            request=lambda: request(latitude, longitude),
            validate=validate,
            min_refresh_seconds=self.open_meteo_refresh_seconds,
            max_stale_seconds=self.current_max_age_seconds,
            strip_coordinates=True,
        )

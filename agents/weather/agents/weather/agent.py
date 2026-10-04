from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .ai_enhance import get_deterministic_urdu_enhancement
from .cache import WeatherCache
from .providers import (
    CURRENT_MAX_AGE_SECONDS,
    FORECAST_MAX_STALE_SECONDS,
    OPEN_METEO_REFRESH_SECONDS,
    PMD_CURRENT_URL,
    PMD_REFRESH_SECONDS,
    WeatherProviderClient,
)
from .schema import (
    CurrentWeather,
    DailyForecast,
    HourlyForecast,
    SourceRecord,
    WeatherAgentResponse,
    WeatherDetails,
)

VERSION = "3.0.0"
PROVIDER = "PMD FFD + Open-Meteo"
DEFAULT_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
DOCS_URL = "https://open-meteo.com/en/docs"
LOCAL_TIMEZONE = "Asia/Karachi"
MAX_CURRENT_AGE_SECONDS = 6 * 60 * 60
MAX_STALE_CACHE_SECONDS = int(
    os.getenv("WEATHER_CURRENT_MAX_CACHE_AGE_SECONDS", str(CURRENT_MAX_AGE_SECONDS))
)
MAX_RESPONSE_BYTES = 5_000_000

BAHAWALPUR_TEHSILS: dict[str, dict[str, float | str]] = {
    "bahawalpur_sadar": {
        "name": "Bahawalpur Sadar",
        "lat": 29.3956,
        "lon": 71.6836,
        "elevation_m": 116.0,
    },
    "ahmadpur_east": {
        "name": "Ahmadpur East",
        "lat": 29.1431,
        "lon": 71.2599,
        "elevation_m": 108.0,
    },
    "yazman": {"name": "Yazman", "lat": 29.1211, "lon": 71.7456, "elevation_m": 112.0},
    "hasilpur": {
        "name": "Hasilpur",
        "lat": 29.6967,
        "lon": 72.5542,
        "elevation_m": 130.0,
    },
    "khairpur_tamewali": {
        "name": "Khairpur Tamewali",
        "lat": 29.5806,
        "lon": 72.2478,
        "elevation_m": 125.0,
    },
}

# WMO weather interpretation codes returned by Open-Meteo.
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherAgent:
    """Evidence-first Bahawalpur weather provider adapter.

    Compatibility surface for KisanOS backend:
      - resolve_coordinates(area_code, lat, lon)
      - fetch_live_weather(lat, lon) -> Open-Meteo-compatible mapping
      - analyze(...) -> validated WeatherAgentResponse

    No crop-health thresholds or synthetic weather values are produced.
    """

    def __init__(
        self,
        open_meteo_url: str | None = None,
        cache_path: str | None = None,
        timeout_seconds: float | None = None,
        retries: int | None = None,
        pmd_current_url: str | None = None,
        pmd_refresh_seconds: int | None = None,
        open_meteo_refresh_seconds: int | None = None,
        current_max_age_seconds: int | None = None,
        forecast_max_stale_seconds: int | None = None,
    ) -> None:
        self.api_url = (
            open_meteo_url or os.getenv("OPEN_METEO_URL") or DEFAULT_ENDPOINT
        ).strip()
        parsed = urllib.parse.urlsplit(self.api_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("OPEN_METEO_URL must be an HTTP(S) endpoint")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.getenv("WEATHER_HTTP_TIMEOUT_SECONDS", "3.5"))
        )
        self.retries = (
            retries if retries is not None else int(os.getenv("WEATHER_RETRIES", "1"))
        )
        if not 0 < self.timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be in (0, 30]")
        if not 0 <= self.retries <= 4:
            raise ValueError("retries must be between 0 and 4")
        self.version = VERSION
        self.cache = WeatherCache(cache_path)
        self.provider_client = WeatherProviderClient(
            self.cache,
            pmd_current_url=pmd_current_url
            or os.getenv("PMD_WEATHER_CURRENT_URL", PMD_CURRENT_URL),
            open_meteo_url=self.api_url,
            timeout_seconds=self.timeout_seconds,
            retries=self.retries,
            pmd_refresh_seconds=pmd_refresh_seconds
            or int(os.getenv("PMD_MIN_REFRESH_SECONDS", str(PMD_REFRESH_SECONDS))),
            open_meteo_refresh_seconds=open_meteo_refresh_seconds
            or int(
                os.getenv(
                    "OPEN_METEO_MIN_REFRESH_SECONDS", str(OPEN_METEO_REFRESH_SECONDS)
                )
            ),
            current_max_age_seconds=current_max_age_seconds
            or int(
                os.getenv(
                    "WEATHER_CURRENT_MAX_CACHE_AGE_SECONDS",
                    str(CURRENT_MAX_AGE_SECONDS),
                )
            ),
            forecast_max_stale_seconds=forecast_max_stale_seconds
            or int(
                os.getenv(
                    "WEATHER_FORECAST_MAX_CACHE_AGE_SECONDS",
                    str(FORECAST_MAX_STALE_SECONDS),
                )
            ),
        )

    @staticmethod
    def _normalize_area(area: str) -> str:
        return area.strip().lower().replace(" ", "_").replace("-", "_")

    def resolve_coordinates(
        self,
        tehsil_or_coords: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> tuple[str, float, float, float | None]:
        """Resolve one of the five pilot tehsils or an explicitly supplied coordinate pair.

        Consent is enforced by `analyze` and by the backend before it calls this compatibility
        helper. Unknown area names and incomplete coordinate pairs fail rather than silently
        selecting Bahawalpur Sadar.
        """
        if (lat is None) != (lon is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        if lat is not None and lon is not None:
            if not math.isfinite(float(lat)) or not math.isfinite(float(lon)):
                raise ValueError("Coordinates must be finite numbers")
            if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
                raise ValueError(
                    "Coordinates are outside the valid latitude/longitude range"
                )
            if not (28.2 <= float(lat) <= 30.5 and 70.4 <= float(lon) <= 73.2):
                raise ValueError(
                    "Coordinates are outside the configured Bahawalpur pilot area"
                )
            return "Consented coordinates", float(lat), float(lon), None
        if tehsil_or_coords is None:
            raise ValueError(
                "Select a supported Bahawalpur tehsil or supply consented coordinates"
            )
        key = self._normalize_area(tehsil_or_coords)
        if key not in BAHAWALPUR_TEHSILS:
            raise ValueError(f"Unsupported Bahawalpur pilot area: {tehsil_or_coords}")
        area = BAHAWALPUR_TEHSILS[key]
        return (
            str(area["name"]),
            float(area["lat"]),
            float(area["lon"]),
            float(area["elevation_m"]),
        )

    @staticmethod
    def _location_key(latitude: float, longitude: float, endpoint: str) -> str:
        return WeatherCache.key(latitude, longitude, endpoint)

    def _request(self, latitude: float, longitude: float) -> dict[str, Any]:
        params = {
            "latitude": f"{latitude:.6f}",
            "longitude": f"{longitude:.6f}",
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,weather_code",
            "forecast_days": "7",
            "forecast_hours": "72",
            "timezone": LOCAL_TIMEZONE,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }
        query = urllib.parse.urlencode(params)
        url = f"{self.api_url}{'&' if '?' in self.api_url else '?'}{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": f"KisanOS-WeatherAgent/{VERSION}",
            },
            method="GET",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError(
                        "Weather provider response exceeded the 5 MB limit"
                    )
                payload = json.loads(body.decode("utf-8"))
                if not self._valid_provider_payload(payload):
                    raise ValueError("Weather provider response failed schema checks")
                return payload
            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(0.25 * (2**attempt), 1.0))
        raise RuntimeError(
            f"Open-Meteo request failed after {self.retries + 1} attempts"
        ) from last_error

    @staticmethod
    def _valid_provider_payload(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        current = payload.get("current")
        daily = payload.get("daily")
        if not isinstance(current, dict) or not isinstance(daily, dict):
            return False
        if not isinstance(payload.get("timezone"), str) or not payload["timezone"]:
            return False
        try:
            zone = ZoneInfo(payload["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            return False
        # Require a provider timestamp before data can be cached or presented as current.
        if not isinstance(current.get("time"), str) or not current["time"]:
            return False
        if WeatherAgent._parse_time(current["time"], zone) is None:
            return False
        if not any(
            WeatherAgent._number(current, key, low, high) is not None
            for key, low, high in (
                ("temperature_2m", -80, 65),
                ("relative_humidity_2m", 0, 100),
                ("precipitation", 0, 1000),
                ("weather_code", 0, 99),
                ("wind_speed_10m", 0, 500),
            )
        ):
            return False
        return (
            isinstance(daily.get("time", []), list)
            and ("hourly" not in payload or isinstance(payload["hourly"], dict))
            and (
                "current_units" not in payload
                or isinstance(payload["current_units"], dict)
            )
        )

    def fetch_live_weather(self, lat: float, lon: float) -> dict[str, Any]:
        """Backward-compatible Open-Meteo bundle method, with bounded caching and provenance.

        The KisanOS backend now uses `fetch_pmd_weather` for current conditions and
        `fetch_open_meteo_outlook` for 3-/7-day forecasts. This legacy method remains for
        callers that already depend on the old method name; it is not used to select the
        farmer-facing current-condition source.
        """
        _, resolved_lat, resolved_lon, _ = self.resolve_coordinates(None, lat, lon)
        return self.provider_client.fetch_open_meteo_current_bundle(
            resolved_lat, resolved_lon, self._request, self._valid_provider_payload
        )

    def fetch_pmd_weather(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch the official PMD FFD station observation and documented 12-hour forecast."""
        _, resolved_lat, resolved_lon, _ = self.resolve_coordinates(None, lat, lon)
        return self.provider_client.fetch_pmd_current(resolved_lat, resolved_lon)

    def fetch_open_meteo_outlook(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch only Open-Meteo's documented hourly 72-hour and seven-day outlook fields."""
        _, resolved_lat, resolved_lon, _ = self.resolve_coordinates(None, lat, lon)
        return self.provider_client.fetch_open_meteo_outlook(resolved_lat, resolved_lon)

    @staticmethod
    def get_resilient_fallback_weather(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        """Deprecated compatibility method. Synthetic weather is deliberately disabled."""
        raise RuntimeError(
            "Synthetic weather fallback is disabled; use a fresh or explicitly stale provider cache"
        )

    @staticmethod
    def _number(
        container: dict[str, Any], key: str, minimum: float, maximum: float
    ) -> float | None:
        raw = container.get(key)
        if raw is None or isinstance(raw, bool):
            return None
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None
        return (
            number if math.isfinite(number) and minimum <= number <= maximum else None
        )

    @staticmethod
    def _parse_time(value: Any, zone: ZoneInfo) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(
                value[:-1] + "+00:00" if value.endswith("Z") else value
            )
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        return parsed.astimezone(UTC)

    @staticmethod
    def _iso_local(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def _current(self, raw: dict[str, Any]) -> CurrentWeather | None:
        values = raw.get("current") or {}
        temperature = self._number(values, "temperature_2m", -80, 65)
        humidity = self._number(values, "relative_humidity_2m", 0, 100)
        precipitation = self._number(values, "precipitation", 0, 1000)
        wind = self._number(values, "wind_speed_10m", 0, 500)
        direction = self._number(values, "wind_direction_10m", 0, 360)
        code_number = self._number(values, "weather_code", 0, 99)
        weather_code = int(code_number) if code_number is not None else None
        description = (
            WMO_WEATHER_CODES.get(weather_code, "Weather code unavailable")
            if weather_code is not None
            else "Weather code unavailable"
        )
        if all(
            item is None
            for item in (
                temperature,
                humidity,
                precipitation,
                wind,
                direction,
                weather_code,
            )
        ):
            return None
        return CurrentWeather(
            time=self._iso_local(values.get("time")),
            temperature_c=temperature,
            relative_humidity_pct=int(humidity) if humidity is not None else None,
            precipitation_mm_previous_hour=precipitation,
            wind_speed_kmh=wind,
            wind_direction_deg=int(direction) if direction is not None else None,
            weather_code=weather_code,
            description=description,
        )

    def _hourly(
        self, raw: dict[str, Any], zone: ZoneInfo, now: datetime
    ) -> list[HourlyForecast]:
        data = raw.get("hourly") or {}
        times = data.get("time") or []
        result: list[HourlyForecast] = []
        for index, time_value in enumerate(times):
            parsed = self._parse_time(time_value, zone)
            if (
                parsed is None
                or parsed < now - timedelta(hours=1)
                or parsed > now + timedelta(hours=73)
            ):
                continue

            def number(
                field: str,
                low: float,
                high: float,
                index: int = index,
                data: dict[str, Any] = data,
            ) -> float | None:
                series = data.get(field) or []
                return (
                    self._number({field: series[index]}, field, low, high)
                    if index < len(series)
                    else None
                )

            weather_code_num = number("weather_code", 0, 99)
            result.append(
                HourlyForecast(
                    time=str(time_value),
                    temperature_c=number("temperature_2m", -80, 65),
                    relative_humidity_pct=int(number("relative_humidity_2m", 0, 100))
                    if number("relative_humidity_2m", 0, 100) is not None
                    else None,
                    precipitation_probability_pct=int(
                        number("precipitation_probability", 0, 100)
                    )
                    if number("precipitation_probability", 0, 100) is not None
                    else None,
                    precipitation_mm=number("precipitation", 0, 1000),
                    wind_speed_kmh=number("wind_speed_10m", 0, 500),
                    wind_direction_deg=int(number("wind_direction_10m", 0, 360))
                    if number("wind_direction_10m", 0, 360) is not None
                    else None,
                    weather_code=int(weather_code_num)
                    if weather_code_num is not None
                    else None,
                )
            )
            if len(result) == 72:
                break
        return result

    def _daily(self, raw: dict[str, Any]) -> list[DailyForecast]:
        data = raw.get("daily") or {}
        times = data.get("time") or []
        result: list[DailyForecast] = []
        for index, day in enumerate(times[:7]):

            def number(
                field: str,
                low: float,
                high: float,
                index: int = index,
                data: dict[str, Any] = data,
            ) -> float | None:
                series = data.get(field) or []
                return (
                    self._number({field: series[index]}, field, low, high)
                    if index < len(series)
                    else None
                )

            code_value = number("weather_code", 0, 99)
            code = int(code_value) if code_value is not None else None
            result.append(
                DailyForecast(
                    date=str(day),
                    temperature_max_c=number("temperature_2m_max", -80, 65),
                    temperature_min_c=number("temperature_2m_min", -80, 65),
                    precipitation_sum_mm=number("precipitation_sum", 0, 5000),
                    precipitation_probability_max_pct=int(
                        number("precipitation_probability_max", 0, 100)
                    )
                    if number("precipitation_probability_max", 0, 100) is not None
                    else None,
                    wind_speed_max_kmh=number("wind_speed_10m_max", 0, 500),
                    weather_code=code,
                    description=WMO_WEATHER_CODES.get(code, "Weather code unavailable")
                    if code is not None
                    else "Weather code unavailable",
                )
            )
        return result

    @staticmethod
    def _unavailable(
        assessment_id: str, created_at: str, message: str
    ) -> WeatherAgentResponse:
        return WeatherAgentResponse(
            assessment_id=assessment_id,
            status="unavailable",
            summary=message,
            observations=[],
            possible_causes=[],
            checks=[],
            evidence_band="not_calibrated",
            evidence_reason="No usable provider response or sufficiently recent cache was available; no weather values were invented.",
            sources=[],
            provider_or_model="open-meteo-unavailable",
            version=VERSION,
            created_at=created_at,
            safety_flags=["weather_unavailable", "no_synthetic_fallback"],
        )

    def analyze(
        self,
        assessment_id: str | None = None,
        tehsil_or_coords: str | None = "bahawalpur_sadar",
        lat: float | None = None,
        lon: float | None = None,
        enable_ai: bool = True,
        gps_consent: bool = False,
        locale: str = "en",
    ) -> WeatherAgentResponse:
        """Return separate PMD current/12-hour and Open-Meteo 72-hour/7-day products.

        Exact farmer coordinates are accepted only with explicit consent. The PMD API resolves
        them to its nearest city/station; neither provider output is represented as field-level.
        """
        if locale not in {"en", "ur", "roman_ur"}:
            raise ValueError("locale must be en, ur, or roman_ur")
        custom_coordinates = lat is not None or lon is not None
        if custom_coordinates and not gps_consent:
            raise ValueError("Exact coordinates require explicit GPS consent")
        location_name, resolved_lat, resolved_lon, _elevation = (
            self.resolve_coordinates(
                tehsil_or_coords if not custom_coordinates else None, lat, lon
            )
        )
        assessment_id = assessment_id or str(uuid.uuid4())
        now = datetime.now(UTC)
        created_at = now.isoformat()

        # Each public provider is independently isolated: either panel can still be useful.
        try:
            pmd = self.fetch_pmd_weather(resolved_lat, resolved_lon)
            pmd_error = None
        except Exception as exc:  # noqa: BLE001 - provider failure must not block the other forecast.
            pmd, pmd_error = None, type(exc).__name__
        try:
            open_meteo = self.fetch_open_meteo_outlook(resolved_lat, resolved_lon)
            open_meteo_error = None
        except Exception as exc:  # noqa: BLE001 - provider failure must not block the other observation.
            open_meteo, open_meteo_error = None, type(exc).__name__

        # Provider retrieval timestamps are generated during the calls above; compare them
        # with a post-fetch clock to avoid labelling a just-returned response future/stale.
        now = datetime.now(UTC)
        pmd_meta = (
            (pmd or {}).get("_kisanos_weather")
            if isinstance((pmd or {}).get("_kisanos_weather"), dict)
            else {}
        )
        pmd_cache_status = pmd_meta.get("cache_status", "unavailable")
        pmd_retrieved_at = pmd_meta.get("source_fetch_at")
        pmd_retrieved_time = self._parse_time(
            pmd_retrieved_at, ZoneInfo(LOCAL_TIMEZONE)
        )
        pmd_retrieval_age = (
            (now - pmd_retrieved_time).total_seconds() if pmd_retrieved_time else None
        )
        pmd_observed_at = (pmd or {}).get("observed_at")
        pmd_observed_time = self._parse_time(pmd_observed_at, ZoneInfo(LOCAL_TIMEZONE))
        pmd_observation_age = (
            (now - pmd_observed_time).total_seconds() if pmd_observed_time else None
        )
        pmd_current = None
        pmd_current_status = "unavailable"
        pmd_current_values: dict[str, Any] = {}
        pmd_city = (
            (pmd or {}).get("city") if isinstance((pmd or {}).get("city"), dict) else {}
        )
        pmd_station = (pmd or {}).get("station")
        if (
            pmd
            and pmd_observation_age is not None
            and 0 <= pmd_observation_age <= CURRENT_MAX_AGE_SECONDS
            and pmd_retrieved_time is not None
        ):
            pmd_current_values = {
                "temperature_c": self._number(pmd, "temperature", -80, 65),
                "relative_humidity_pct": self._number(pmd, "humidity_pct", 0, 100),
                "rainfall_mm": self._number(pmd, "rainfall_mm", 0, 5000),
                "rainfall_24h_mm": self._number(pmd, "rainfall_24h_mm", 0, 5000),
                "wind_speed_kmh": self._number(pmd, "wind_kmh", 0, 500),
                "wind_direction": pmd.get("wind_direction")
                if isinstance(pmd.get("wind_direction"), str)
                else None,
                "dew_point_c": self._number(pmd, "dew_point", -100, 65),
                "pressure_hpa": self._number(pmd, "pressure_hpa", 0, 1200),
                "visibility_km": self._number(pmd, "visibility", 0, 500),
                "station": pmd_station if isinstance(pmd_station, str) else None,
                "source_time": pmd_observed_at,
            }
            condition = (
                pmd.get("condition") if isinstance(pmd.get("condition"), dict) else {}
            )
            description = (
                condition.get("label")
                if isinstance(condition.get("label"), str)
                else "PMD condition unavailable"
            )
            pmd_current = CurrentWeather(
                time=pmd_observed_at,
                temperature_c=pmd_current_values["temperature_c"],
                relative_humidity_pct=int(pmd_current_values["relative_humidity_pct"])
                if pmd_current_values["relative_humidity_pct"] is not None
                else None,
                rainfall_mm=pmd_current_values["rainfall_mm"],
                rainfall_24h_mm=pmd_current_values["rainfall_24h_mm"],
                wind_speed_kmh=pmd_current_values["wind_speed_kmh"],
                wind_direction=pmd_current_values["wind_direction"],
                dew_point_c=pmd_current_values["dew_point_c"],
                pressure_hpa=pmd_current_values["pressure_hpa"],
                visibility_km=pmd_current_values["visibility_km"],
                station=pmd_current_values["station"],
                source_time=pmd_observed_at,
                description=description,
            )
            pmd_current_status = (
                "stale"
                if pmd_cache_status == "stale"
                or (pmd or {}).get("is_live") is False
                or pmd_retrieval_age is None
                or pmd_retrieval_age < 0
                else "fresh"
            )

        pmd_forecast = (
            (pmd or {}).get("forecast")
            if isinstance((pmd or {}).get("forecast"), dict)
            else {}
        )
        pmd_hours_raw = (
            pmd_forecast.get("hours")
            if isinstance(pmd_forecast.get("hours"), list)
            else []
        )
        pmd_cycle = pmd_forecast.get("cycle")
        pmd_run_time = None
        if isinstance(pmd_cycle, str) and len(pmd_cycle) == 10 and pmd_cycle.isdigit():
            try:
                pmd_run_time = datetime.strptime(pmd_cycle, "%Y%m%d%H").replace(
                    tzinfo=UTC
                )
            except ValueError:
                pmd_run_time = None
        pmd_forecast_age = (
            (now - pmd_run_time).total_seconds() if pmd_run_time else None
        )
        pmd_hourly_12h = []
        for row in pmd_hours_raw[:12]:
            if not isinstance(row, dict):
                continue
            pmd_hourly_12h.append(
                {
                    "time": row.get("at"),
                    "temperature_c": self._number(row, "temp", -80, 65),
                    "precipitation_mm": self._number(row, "rain_mm", 0, 1000),
                    "condition": row.get("condition")
                    if isinstance(row.get("condition"), str)
                    else None,
                    "provider": "PMD FFD",
                    "units": {"temperature": "°C", "precipitation": "mm"},
                }
            )
        pmd_forecast_status = "unavailable"
        if len(pmd_hourly_12h) == 12 and pmd_retrieved_time is not None:
            pmd_forecast_status = (
                "stale"
                if pmd_cache_status == "stale"
                or pmd_retrieval_age is None
                or pmd_retrieval_age < 0
                or (
                    pmd_forecast_age is not None
                    and (
                        pmd_forecast_age < -3600
                        or pmd_forecast_age > CURRENT_MAX_AGE_SECONDS
                    )
                )
                else "fresh"
            )

        om_meta = (
            (open_meteo or {}).get("_kisanos_weather")
            if isinstance((open_meteo or {}).get("_kisanos_weather"), dict)
            else {}
        )
        om_cache_status = om_meta.get("cache_status", "unavailable")
        om_retrieved_at = om_meta.get("source_fetch_at")
        timezone_name = str((open_meteo or {}).get("timezone") or LOCAL_TIMEZONE)
        try:
            zone = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            zone = ZoneInfo(LOCAL_TIMEZONE)
            open_meteo, om_cache_status, open_meteo_error = (
                None,
                "unavailable",
                "InvalidTimezone",
            )
        om_retrieved_time = self._parse_time(om_retrieved_at, zone)
        om_retrieval_age = (
            (now - om_retrieved_time).total_seconds() if om_retrieved_time else None
        )
        hourly = self._hourly(open_meteo or {}, zone, now)
        daily = self._daily(open_meteo or {})
        om_freshness = "unavailable"
        if open_meteo and (hourly or daily):
            om_freshness = (
                "stale"
                if om_cache_status == "stale"
                or om_retrieved_time is None
                or om_retrieval_age is None
                or om_retrieval_age < 0
                else "fresh"
            )
        pmd_current_weather_status = f"weather_{pmd_current_status}"
        pmd_forecast_weather_status = f"weather_{pmd_forecast_status}"
        om_weather_status = f"weather_{om_freshness}"
        statuses = [pmd_current_status, pmd_forecast_status, om_freshness]
        usable_statuses = [value for value in statuses if value in {"fresh", "stale"}]
        fresh_count = statuses.count("fresh")
        if fresh_count == len(statuses) and fresh_count == 3:
            status = "complete"
        elif fresh_count:
            status = "partial"
        elif usable_statuses:
            status = "stale"
        else:
            status = "unavailable"
        freshness = (
            "fresh" if fresh_count else "stale" if usable_statuses else "unavailable"
        )
        resolved_pmd_name = (
            pmd_city.get("name")
            if isinstance(pmd_city.get("name"), str)
            else location_name
        )
        current_temp = pmd_current.temperature_c if pmd_current else None
        current_humidity = pmd_current.relative_humidity_pct if pmd_current else None
        current_wind = pmd_current.wind_speed_kmh if pmd_current else None
        summary = (
            f"PMD current/12-hour station products and Open-Meteo 72-hour/seven-day outlooks were evaluated separately for {resolved_pmd_name}. "
            f"Provider freshness is {freshness}; these are nearby weather grid or station context, not field measurements or a crop diagnosis."
        )

        observations: list[str] = []
        weather_watch_signals: list[dict[str, Any]] = []
        if pmd_current:
            observations.append(
                f"PMD reports current station conditions for {resolved_pmd_name} at {pmd_station or 'the resolved station'}; this is not a field measurement."
            )
            if current_temp is not None:
                observations.append(
                    f"PMD-reported station temperature: {current_temp:g} °C."
                )
            if current_humidity is not None:
                observations.append(
                    f"PMD-reported relative humidity: {current_humidity:g}%."
                )
            if current_wind is not None:
                observations.append(f"PMD-reported wind speed: {current_wind:g} km/h.")
            if pmd_current.rainfall_mm is not None:
                observations.append(
                    f"PMD-reported rainfall: {pmd_current.rainfall_mm:g} mm (source reporting interval not inferred)."
                )
            if pmd_current.rainfall_24h_mm is not None:
                observations.append(
                    f"PMD-reported 24-hour rainfall: {pmd_current.rainfall_24h_mm:g} mm."
                )
        if pmd_hourly_12h:
            pmd_rainfall = [
                row["precipitation_mm"]
                for row in pmd_hourly_12h
                if row.get("precipitation_mm") is not None
            ]
            observations.append(
                "PMD's documented hourly-interpolated 12-hour forecast is shown as a separate provider product."
                + (
                    f" Maximum hourly rainfall shown: {max(pmd_rainfall):g} mm."
                    if pmd_rainfall
                    else ""
                )
            )
        hourly_rain = [
            row.precipitation_mm for row in hourly if row.precipitation_mm is not None
        ]
        hourly_probability = [
            row.precipitation_probability_pct
            for row in hourly
            if row.precipitation_probability_pct is not None
        ]
        daily_rain = [
            row.precipitation_sum_mm
            for row in daily
            if row.precipitation_sum_mm is not None
        ]
        daily_probability = [
            row.precipitation_probability_max_pct
            for row in daily
            if row.precipitation_probability_max_pct is not None
        ]
        if hourly:
            hourly_summary = (
                "Open-Meteo's next-72-hour forecast is shown separately from PMD."
            )
            if hourly_rain:
                hourly_summary += (
                    f" Maximum hourly precipitation shown: {max(hourly_rain):g} mm."
                )
            if hourly_probability:
                hourly_summary += (
                    f" Maximum hourly precipitation probability: {max(hourly_probability):g}% "
                    "(event probability, not forecast confidence)."
                )
            observations.append(hourly_summary)
        if daily:
            daily_summary = (
                "Open-Meteo's seven-day outlook is shown separately from PMD."
            )
            if daily_rain:
                daily_summary += (
                    f" Maximum daily precipitation total shown: {max(daily_rain):g} mm."
                )
            if daily_probability:
                daily_summary += (
                    f" Maximum daily precipitation probability: {max(daily_probability):g}% "
                    "(event probability, not forecast confidence)."
                )
            observations.append(daily_summary)
        if hourly and (
            (hourly_rain and max(hourly_rain) > 0)
            or (hourly_probability and max(hourly_probability) > 0)
        ):
            weather_watch_signals.append(
                {
                    "signal": "forecast_precipitation_next_72h",
                    "provider": "Open-Meteo",
                    "maximum_hourly_precipitation_mm": max(hourly_rain)
                    if hourly_rain
                    else None,
                    "maximum_hourly_precipitation_probability_pct": max(
                        hourly_probability
                    )
                    if hourly_probability
                    else None,
                    "interpretation": "Forecast watch only; not a field observation, crop-risk rating, or forecast-confidence score.",
                }
            )
        if daily and (
            (daily_rain and max(daily_rain) > 0)
            or (daily_probability and max(daily_probability) > 0)
        ):
            weather_watch_signals.append(
                {
                    "signal": "forecast_precipitation_next_7d",
                    "provider": "Open-Meteo",
                    "maximum_daily_precipitation_total_mm": max(daily_rain)
                    if daily_rain
                    else None,
                    "maximum_daily_precipitation_probability_pct": max(
                        daily_probability
                    )
                    if daily_probability
                    else None,
                    "interpretation": "Forecast watch only; not a field observation, crop-risk rating, or forecast-confidence score.",
                }
            )
        if not observations:
            observations.append(
                "No usable provider values were returned; no substitute weather was generated."
            )

        providers = {
            "pmd": {
                "provider": "Pakistan Meteorological Department — Flood Forecasting Division",
                "source_url": "https://ffd.pmd.gov.pk/weather-widget",
                "weather_status": "weather_partial"
                if "stale" in {pmd_current_status, pmd_forecast_status}
                and "fresh" in {pmd_current_status, pmd_forecast_status}
                else f"weather_{'fresh' if 'fresh' in {pmd_current_status, pmd_forecast_status} else 'stale' if 'stale' in {pmd_current_status, pmd_forecast_status} else 'unavailable'}",
                "cache": {
                    "status": pmd_cache_status,
                    "age_seconds": pmd_meta.get("cache_age_seconds"),
                },
                "snapshot_sha256": pmd_meta.get("snapshot_sha256"),
                "location_resolution": {
                    "selected_area": location_name,
                    "resolved_city": resolved_pmd_name,
                    "province": pmd_city.get("province"),
                    "station": pmd_station,
                    "wmo_codes": pmd_city.get("wmo_codes"),
                    "granularity": "nearest_city_station",
                    "field_level_precision_claimed": False,
                },
                "current": {
                    "status": pmd_current_status,
                    "weather_status": pmd_current_weather_status,
                    "observed_at": pmd_observed_at,
                    "retrieved_at": pmd_retrieved_at,
                    "timezone": LOCAL_TIMEZONE,
                    "freshness_age_seconds": int(pmd_observation_age)
                    if pmd_observation_age is not None
                    else None,
                    "units": {
                        "temperature": "°C",
                        "humidity": "%",
                        "rainfall": "mm",
                        "wind_speed": "km/h",
                        "pressure": "hPa",
                        "visibility": "km",
                    },
                    "values": pmd_current.model_dump(mode="json")
                    if pmd_current
                    else None,
                    "reason": pmd_error
                    or (
                        "observation timestamp is missing or older than six hours"
                        if pmd_current_status == "unavailable"
                        else None
                    ),
                },
                "forecast_12h": {
                    "status": pmd_forecast_status,
                    "weather_status": pmd_forecast_weather_status,
                    "retrieved_at": pmd_retrieved_at,
                    "forecast_issue_at": pmd_run_time.isoformat()
                    if pmd_run_time
                    else None,
                    "forecast_model": pmd_forecast.get("name"),
                    "forecast_model_organization": pmd_forecast.get("organization")
                    or pmd_forecast.get("org"),
                    "timezone": LOCAL_TIMEZONE,
                    "units": {"temperature": "°C", "precipitation": "mm"},
                    "interpolation": "hourly_interpolated_by_PMD_from_numerical_model",
                    "hourly": pmd_hourly_12h
                    if pmd_forecast_status != "unavailable"
                    else [],
                    "reason": pmd_error
                    or (
                        "PMD returned no usable 12-hour forecast"
                        if pmd_forecast_status == "unavailable"
                        else None
                    ),
                },
            },
            "open_meteo": {
                "provider": "Open-Meteo",
                "source_url": DOCS_URL,
                "weather_status": om_weather_status,
                "cache": {
                    "status": om_cache_status,
                    "age_seconds": om_meta.get("cache_age_seconds"),
                },
                "snapshot_sha256": om_meta.get("snapshot_sha256"),
                "location_resolution": {
                    "selected_area": location_name,
                    "granularity": "forecast_grid_near_selected_area",
                    "field_level_precision_claimed": False,
                },
                "forecast_issue_at": None,
                "forecast_issue_note": "The queried Open-Meteo response fields do not expose a verified model-run timestamp; API generation time is not a model issue time.",
                "timezone": timezone_name,
                "hourly_72h": {
                    "status": om_freshness,
                    "weather_status": om_weather_status,
                    "retrieved_at": om_retrieved_at,
                    "units": {
                        "temperature": "°C",
                        "humidity": "%",
                        "precipitation": "mm",
                        "precipitation_probability": "%",
                        "wind_speed": "km/h",
                        "wind_direction": "°",
                    },
                    "precipitation_probability_note": "Probability of precipitation only; not forecast confidence.",
                    "values": [row.model_dump(mode="json") for row in hourly],
                    "reason": open_meteo_error,
                },
                "daily_7d": {
                    "status": om_freshness,
                    "weather_status": om_weather_status,
                    "retrieved_at": om_retrieved_at,
                    "units": {
                        "temperature": "°C",
                        "precipitation": "mm",
                        "precipitation_probability": "%",
                        "wind_speed": "km/h",
                    },
                    "precipitation_probability_note": "Probability of precipitation only; not forecast confidence.",
                    "values": [row.model_dump(mode="json") for row in daily],
                    "reason": open_meteo_error,
                },
            },
        }
        pmd_source = SourceRecord(
            title="PMD FFD weather widget JSON product",
            url="https://ffd.pmd.gov.pk/weather-widget",
            publisher="Pakistan Meteorological Department — Flood Forecasting Division",
            retrieved_at=pmd_retrieved_at,
            source_status="official",
            note="PMD current station observation and documented 12-hour hourly-interpolated forecast; source products retain separate timestamps and freshness.",
        )
        om_source = SourceRecord(
            title="Open-Meteo Forecast API documentation",
            url=DOCS_URL,
            publisher="Open-Meteo",
            retrieved_at=om_retrieved_at,
            source_status="official",
            note="Used only for the 72-hour/7-day outlook; no local accuracy or model confidence is claimed.",
        )
        provider_times = [
            self._parse_time(value, ZoneInfo(LOCAL_TIMEZONE))
            for value in (pmd_retrieved_at, om_retrieved_at)
            if value
        ]
        most_recent_source_retrieval = (
            max(provider_times).isoformat() if provider_times else None
        )
        details = WeatherDetails(
            location_name=str(resolved_pmd_name),
            location_granularity="consented_coordinate_forecast_grid"
            if custom_coordinates
            else "tehsil_forecast_grid",
            timezone=timezone_name,
            provider_current_time=pmd_observed_at,
            provider_model_run_time=pmd_run_time.isoformat() if pmd_run_time else None,
            provider_model_run_time_note="PMD's forecast cycle is reported when present; Open-Meteo does not expose a verified model-run time in the selected response fields.",
            retrieved_at=most_recent_source_retrieval,
            units={
                "temperature": "°C",
                "relative_humidity": "%",
                "precipitation": "mm",
                "wind_speed": "km/h",
            },
            freshness=freshness,
            cache_status="stale"
            if "stale" in statuses
            else "live"
            if "fresh" in statuses
            else "unavailable",
            cache_age_seconds=max(
                (
                    int(value)
                    for value in (
                        pmd_meta.get("cache_age_seconds"),
                        om_meta.get("cache_age_seconds"),
                    )
                    if isinstance(value, (int, float))
                ),
                default=None,
            ),
            current=pmd_current,
            hourly_next_72h=hourly,
            daily_outlook_7d=daily,
            weather_watch_signals=weather_watch_signals,
            providers=providers,
        )
        sources = [pmd_source, om_source]
        if enable_ai:
            enhanced = get_deterministic_urdu_enhancement(
                {
                    "tehsil": str(resolved_pmd_name),
                    "temperature_c": current_temp,
                    "relative_humidity_pct": current_humidity,
                    "wind_speed_kmh": current_wind,
                    "weather_description": pmd_current.description
                    if pmd_current
                    else "",
                }
            )
        else:
            enhanced = None
        return WeatherAgentResponse(
            assessment_id=assessment_id,
            status=status,
            summary=summary,
            observations=observations,
            possible_causes=(
                [
                    "Forecast precipitation is a possible meteorological context to compare with field observations; it does not establish the cause of any crop symptoms."
                ]
                if weather_watch_signals
                else []
            ),
            checks=[
                "Compare this nearby station/grid forecast with actual farm conditions and check the latest official PMD advisory before making field decisions."
            ],
            evidence_band="low" if fresh_count else "not_calibrated",
            evidence_reason=(
                "PMD current/12-hour data and Open-Meteo 72-hour/7-day outlook retain separate provider, retrieval/run time, location, units, and freshness. City/grid context is not a field measurement."
                if fresh_count
                else "Provider data are stale or unavailable; stale badges are authoritative and no substitute values or agronomic actions are inferred."
            ),
            sources=sources,
            provider_or_model="pmd-ffd+open-meteo",
            version=VERSION,
            created_at=created_at,
            safety_flags=[
                "forecast_grid_not_field_sensor",
                "no_agronomic_thresholds",
                "no_provider_confidence_claims",
                "no_synthetic_fallback",
                "provider_stale_data"
                if "stale" in statuses
                else "provider_products_separated",
            ],
            AI_ENHANCED=enhanced,
            weather_details=details,
        )

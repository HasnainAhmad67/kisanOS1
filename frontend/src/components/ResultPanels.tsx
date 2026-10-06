import type { ReactNode } from "react";
import { useI18n, type DictKey } from "../i18n";
import type {
  InputCompleteness,
  Source,
  WaterCardData,
  WaterContextLabel,
  WeatherCardData,
  WeatherCurrent,
} from "../types/backend";

/* ---------------------------------------------------------------- guards */

/**
 * Structural guard for the Weather card's `data`: the panel only renders the
 * connected adapter's shape, so an unavailable card (no provider values) keeps
 * its plain summary instead of showing empty rows.
 */
export function isWeatherCardData(value: unknown): value is WeatherCardData {
  if (typeof value !== "object" || value === null) return false;
  const data = value as Partial<WeatherCardData>;
  return (
    typeof data.location_name === "string" &&
    typeof data.current === "object" &&
    data.current !== null
  );
}

/** Structural guard for the Water card's structured input-completeness report. */
export function isWaterCardData(value: unknown): value is WaterCardData {
  if (typeof value !== "object" || value === null) return false;
  const data = value as Partial<WaterCardData>;
  const completeness = data.input_completeness;
  return (
    typeof completeness === "object" &&
    completeness !== null &&
    Array.isArray(data.missing_inputs)
  );
}

/* ---------------------------------------------------------------- shared */

/**
 * One label/value row. Values are source data (places, times, provider
 * numbers) so they stay LTR inside the RTL Urdu layout; labels are localized.
 */
function Row({
  label,
  value,
  ltr = true,
}: {
  label: string;
  value: ReactNode;
  /** false for values rendered in the UI language (localized placeholders). */
  ltr?: boolean;
}) {
  return (
    <div className="data-panel__row">
      <dt>{label}</dt>
      <dd
        className={ltr ? "num" : undefined}
        dir={ltr ? "ltr" : undefined}
        lang={ltr ? "en" : undefined}
      >
        {value}
      </dd>
    </div>
  );
}

/** Provider timestamps are ISO strings; never render an invalid date. */
function formatTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleString();
}

/** Raw provider number — no rounding, no conversion, no invented default. */
function measure(value: number | null | undefined, fallback: string): ReactNode {
  return typeof value === "number" && Number.isFinite(value) ? (
    String(value)
  ) : (
    <span className="data-panel__absent">{fallback}</span>
  );
}

/* -------------------------------------------------------------- weather */

const WEATHER_FRESHNESS_KEY: Record<string, DictKey> = {
  fresh: "weather.panel.freshness.fresh",
  stale_or_timestamp_missing: "weather.panel.freshness.stale",
  unavailable: "weather.panel.freshness.unavailable",
};

/**
 * Weather values panel: current conditions with explicit units, the
 * next-24-hour precipitation block, and provider + fetch times. Every number
 * comes from the provider response — absent values are labelled as such and
 * never shown as 0.
 */
export function WeatherPanel({
  data,
  sources,
}: {
  data: WeatherCardData;
  sources: Source[];
}) {
  const { t } = useI18n();
  const current: Partial<WeatherCurrent> = data.current ?? {};
  const window = data.next_24h;
  const freshness = data.freshness ? WEATHER_FRESHNESS_KEY[data.freshness] : undefined;
  const providerSource = sources.find((source) => source.publisher === "Open-Meteo");
  const absent = t("weather.panel.notReported");
  const providerTime = formatTime(data.provider_observation_at);
  const retrievedAt = formatTime(data.retrieved_at);

  return (
    <section className="data-panel" aria-label={t("weather.panel.heading")}>
      <div className="data-panel__head">
        <p className="data-panel__title">{t("weather.panel.heading")}</p>
        {freshness ? (
          <span className={`badge data-panel__badge data-panel__badge--${data.freshness}`}>
            {t(freshness)}
          </span>
        ) : null}
      </div>
      <p className="data-panel__note">
        {data.location_name} — {t("weather.panel.gridNote")}
      </p>
      <dl className="data-panel__grid">
        <Row label={t("weather.panel.temperature")} value={measure(current.temperature_c, absent)} />
        <Row label={t("weather.panel.humidity")} value={measure(current.relative_humidity_pct, absent)} />
        <Row label={t("weather.panel.precipitation")} value={measure(current.precipitation_mm, absent)} />
        <Row label={t("weather.panel.wind")} value={measure(current.wind_speed_kmh, absent)} />
        <Row
          label={t("weather.panel.next24Precip")}
          value={measure(window?.precipitation_total_mm, absent)}
        />
        <Row
          label={t("weather.panel.next24Prob")}
          value={measure(window?.precipitation_probability_max_pct, absent)}
        />
        <Row
          label={t("weather.panel.provider")}
          value={
            providerSource?.url ? (
              <a href={providerSource.url} target="_blank" rel="noreferrer noopener">
                {data.provider ?? providerSource.publisher}
              </a>
            ) : (
              (data.provider ?? providerSource?.publisher ?? "Open-Meteo")
            )
          }
        />
        <Row
          label={t("weather.panel.providerTime")}
          value={providerTime ?? <span className="data-panel__absent">{absent}</span>}
          ltr={providerTime !== null}
        />
        <Row
          label={t("weather.panel.retrieved")}
          value={retrievedAt ?? <span className="data-panel__absent">{absent}</span>}
          ltr={retrievedAt !== null}
        />
      </dl>
    </section>
  );
}

/* ---------------------------------------------------------------- water */

const FIELD_LABELS: { key: keyof InputCompleteness; label: DictKey }[] = [
  { key: "growth_stage", label: "water.field.growthStage" },
  { key: "irrigation_history", label: "water.field.irrigationHistory" },
  { key: "soil_texture", label: "water.field.soilTexture" },
  { key: "soil_moisture", label: "water.field.soilMoisture" },
  { key: "drainage", label: "water.field.drainage" },
  { key: "weather_context", label: "water.field.weatherContext" },
];

const FIELD_STATE_KEY: Record<string, DictKey> = {
  known: "water.field.state.known",
  unknown: "water.field.state.unknown",
  fresh: "water.field.state.fresh",
  stale: "water.field.state.stale",
  unavailable: "water.field.state.unavailable",
};

const WATER_CONTEXT_KEY: Record<WaterContextLabel, DictKey> = {
  field_check_needed: "water.context.field_check_needed",
  watch_drainage: "water.context.watch_drainage",
  forecast_context_only: "water.context.forecast_context_only",
};

/**
 * "Field information": what the farmer reported (green) versus what is still
 * missing (amber), plus the water-context label. No value is inferred — an
 * unknown input stays visibly unknown.
 */
export function FieldInformation({ data }: { data: WaterCardData }) {
  const { t } = useI18n();
  const completeness = data.input_completeness;
  const contextLabel = data.water_context?.label;

  return (
    <section className="data-panel" aria-label={t("water.field.heading")}>
      <div className="data-panel__head">
        <p className="data-panel__title">{t("water.field.heading")}</p>
        {contextLabel && contextLabel in WATER_CONTEXT_KEY ? (
          <span className="badge data-panel__badge data-panel__badge--info">
            {t(WATER_CONTEXT_KEY[contextLabel])}
          </span>
        ) : null}
      </div>
      <ul className="data-chips">
        {FIELD_LABELS.map(({ key, label }) => {
          const state = String(completeness[key]);
          const known = state === "known" || state === "fresh";
          return (
            <li
              key={key}
              className={`chip ${known ? "chip--known" : "chip--missing"}`}
            >
              {t(label)}: {t(FIELD_STATE_KEY[state] ?? "water.field.state.unknown")}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

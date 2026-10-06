import type { ReactNode } from "react";
import { useI18n, type DictKey } from "../i18n";
import type {
  CropCardData,
  InputCompleteness,
  InputRecap,
  NextInformationItem,
  NextInformationKey,
  PhotoAssessmentStatus,
  PhotoReport,
  PhotoSubject,
  ScreeningScope,
  Source,
  VisibleSignCategory,
  WaterCardData,
  WaterContextLabel,
  WeatherCardData,
  WeatherCurrent,
} from "../types/backend";
import { BackendText } from "./BackendText";

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

/**
 * Structural guard for the Crop card's evidence split: the panel only renders
 * when at least one of the structured lists is present, so a legacy or
 * unsupported card keeps its plain summary instead of showing empty sections.
 */
export function isCropCardData(value: unknown): value is CropCardData {
  if (typeof value !== "object" || value === null) return false;
  const data = value as Partial<CropCardData>;
  return (
    Array.isArray(data.farmer_reported_symptoms) ||
    Array.isArray(data.photo_visible_findings) ||
    Array.isArray(data.crop_possibilities) ||
    Array.isArray(data.field_checks) ||
    Array.isArray(data.escalation_signs)
  );
}

/** Only non-empty string lists are rendered, so a section never shows blanks. */
function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item !== "");
}

/**
 * Structural guard for the Vision card's `photo_report`: the panel only
 * renders the gateway's own shape, so a legacy or absent report keeps the
 * card's plain summary and lists instead of showing empty sections.
 */
export function isVisionPhotoReport(value: unknown): value is PhotoReport {
  if (typeof value !== "object" || value === null) return false;
  const report = value as Partial<PhotoReport>;
  return (
    typeof report.assessment_status === "string" &&
    typeof report.visible_sign_category === "string" &&
    typeof report.screening_interpretation === "string" &&
    Array.isArray(report.what_is_visible)
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

/* ------------------------------------------------- water: what is needed next */

const NEXT_INFO_LABEL: Record<NextInformationKey, DictKey> = {
  growth_stage: "water.next.label.growth_stage",
  last_irrigation_date: "water.next.label.last_irrigation_date",
  soil_texture: "water.next.label.soil_texture",
  soil_moisture: "water.next.label.soil_moisture",
  drainage: "water.next.label.drainage",
  weather_context: "water.next.label.weather_context",
};

const NEXT_INFO_REASON: Record<NextInformationKey, DictKey> = {
  growth_stage: "water.next.reason.growth_stage",
  last_irrigation_date: "water.next.reason.last_irrigation_date",
  soil_texture: "water.next.reason.soil_texture",
  soil_moisture: "water.next.reason.soil_moisture",
  drainage: "water.next.reason.drainage",
  weather_context: "water.next.reason.weather_context",
};

/**
 * "What is needed next": the structured report of missing field details
 * (labels and reasons localized here) plus the card's next field checks.
 * Nothing is inferred and no irrigation amount, timing or duration appears.
 */
export function WaterNextInformation({
  data,
  checks,
}: {
  data: WaterCardData;
  checks: string[];
}) {
  const { t } = useI18n();
  const items: NextInformationItem[] = Array.isArray(data.next_information_needed)
    ? data.next_information_needed.filter(
        (item) => item && typeof item.key === "string",
      )
    : [];

  if (items.length === 0) return null;

  return (
    <section className="data-panel" aria-label={t("water.next.heading")}>
      <div className="data-panel__head">
        <p className="data-panel__title">{t("water.next.heading")}</p>
      </div>

      <div className="next-info">
        <p className="next-info__heading">{t("water.next.infoNeeded")}</p>
        <ul className="next-info__list">
          {items.map((item) => (
            <li className="next-info__item" key={item.key}>
              <span className="next-info__label">
                {NEXT_INFO_LABEL[item.key]
                  ? t(NEXT_INFO_LABEL[item.key])
                  : item.label}
              </span>
              <span className="next-info__reason">
                {NEXT_INFO_REASON[item.key]
                  ? t(NEXT_INFO_REASON[item.key])
                  : item.reason}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {checks.length > 0 ? (
        <div className="next-info">
          <p className="next-info__heading">{t("water.next.fieldCheck")}</p>
          <ul className="next-info__list">
            {checks.map((check, index) => (
              <li className="next-info__item" key={index}>
                <BackendText text={check} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------ crop: evidence */

type CropSectionKey =
  | "farmer_reported_symptoms"
  | "photo_visible_findings"
  | "crop_possibilities"
  | "field_checks"
  | "escalation_signs";

/**
 * The five evidence-split sections, in reading order. Each carries its own
 * localized heading so a farmer can see which statements come from them,
 * which come from the photo, and which are only screening possibilities.
 */
const CROP_SECTIONS: { key: CropSectionKey; label: DictKey; modifier: string }[] = [
  {
    key: "farmer_reported_symptoms",
    label: "crop.evidence.farmer",
    modifier: "crop-evidence__list--farmer",
  },
  {
    key: "photo_visible_findings",
    label: "crop.evidence.photo",
    modifier: "crop-evidence__list--photo",
  },
  {
    key: "crop_possibilities",
    label: "crop.evidence.possibilities",
    modifier: "crop-evidence__list--possibilities",
  },
  {
    key: "field_checks",
    label: "crop.evidence.checks",
    modifier: "crop-evidence__list--checks",
  },
  {
    key: "escalation_signs",
    label: "crop.evidence.escalation",
    modifier: "crop-evidence__list--escalation",
  },
];

/**
 * Crop evidence split: farmer-reported symptoms, photo-visible findings,
 * screening possibilities, field checks and escalation signs — each under its
 * own heading so nothing reads as a confirmed cause.
 */
export function CropEvidencePanel({
  data,
  checks,
}: {
  data: CropCardData;
  checks: string[];
}) {
  const { t } = useI18n();

  const sections = CROP_SECTIONS.map((section) => ({
    ...section,
    items: stringList(
      section.key === "field_checks" && !Array.isArray(data.field_checks)
        ? checks
        : data[section.key],
    ),
  })).filter((section) => section.items.length > 0);

  if (sections.length === 0) return null;

  return (
    <section className="data-panel" aria-label={t("crop.evidence.heading")}>
      <div className="data-panel__head">
        <p className="data-panel__title">{t("crop.evidence.heading")}</p>
      </div>
      {sections.map((section) => (
        <div className="crop-evidence" key={section.key}>
          <p className="crop-evidence__label">{t(section.label)}</p>
          <ul className={`crop-evidence__list ${section.modifier}`}>
            {section.items.map((item, index) => (
              <li key={index}>
                <BackendText text={item} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

/* ------------------------------------------------- vision: photo report */

const PHOTO_STATUS_KEY: Record<PhotoAssessmentStatus, DictKey> = {
  assessable: "vision.report.status.assessable",
  limited: "vision.report.status.limited",
  not_assessable: "vision.report.status.not_assessable",
};

/** Status → badge colour: assessable green, limited amber, not assessable red. */
const PHOTO_STATUS_MODIFIER: Record<PhotoAssessmentStatus, string> = {
  assessable: "ok",
  limited: "warn",
  not_assessable: "blocked",
};

const PHOTO_CATEGORY_KEY: Record<VisibleSignCategory, DictKey> = {
  healthy_looking: "vision.report.category.healthy_looking",
  rust_like_marks: "vision.report.category.rust_like_marks",
  unclear: "vision.report.category.unclear",
};

/** Plant part the photo shows — the codes the gateway itself produced. */
const PHOTO_SUBJECT_KEY: Record<PhotoSubject, DictKey> = {
  wheat_leaf: "vision.report.subject.wheat_leaf",
  wheat_ear_or_head: "vision.report.subject.wheat_ear_or_head",
  whole_field_or_distant_crop: "vision.report.subject.whole_field_or_distant_crop",
  other_plant_part: "vision.report.subject.other_plant_part",
  unclear: "vision.report.subject.unclear",
};

/** Whether leaf-sign screening applies to this photo at all. */
const PHOTO_SCOPE_KEY: Record<ScreeningScope, DictKey> = {
  leaf_screening_applicable: "vision.report.scope.leaf_screening_applicable",
  leaf_screening_not_applicable: "vision.report.scope.leaf_screening_not_applicable",
  subject_unclear: "vision.report.scope.subject_unclear",
};

/**
 * Short value for the "Leaf-symptom screening" row, so a farmer reads
 * "Not applicable to this image" instead of a full restated sentence. The
 * longer wording above stays in the collapsed technical details.
 */
const PHOTO_SCOPE_SHORT_KEY: Record<ScreeningScope, DictKey> = {
  leaf_screening_applicable: "vision.report.scopeShort.leaf_screening_applicable",
  leaf_screening_not_applicable: "vision.report.scopeShort.leaf_screening_not_applicable",
  subject_unclear: "vision.report.scopeShort.subject_unclear",
};

/**
 * Neutral scope notice for a CLEAR photo outside leaf-screening scope: blue,
 * never a red error and never a low-quality warning — the photo is fine, it
 * just is not a leaf close-up.
 */
const SCOPE_NOTICE_KEY: Record<PhotoSubject, DictKey> = {
  wheat_leaf: "vision.report.scopeNotice.other",
  wheat_ear_or_head: "vision.report.scopeNotice.ear",
  whole_field_or_distant_crop: "vision.report.scopeNotice.other",
  other_plant_part: "vision.report.scopeNotice.other",
  unclear: "vision.report.scopeNotice.other",
};

/**
 * "Photo screening report": what the photo could be used for, what it shows
 * and does not show, the preliminary interpretation, the next field checks,
 * when to retake, and when an expert review is appropriate.
 *
 * Only the report's own closed codes are read as UI labels; every sentence
 * goes through `<BackendText>` (Urdu when a known wording exists). No model
 * label, score, tensor shape or safety flag is rendered here.
 */
export function PhotoScreeningReport({ report }: { report: PhotoReport }) {
  const { t } = useI18n();
  const status: PhotoAssessmentStatus =
    report.assessment_status in PHOTO_STATUS_KEY ? report.assessment_status : "limited";
  const category: VisibleSignCategory =
    report.visible_sign_category in PHOTO_CATEGORY_KEY
      ? report.visible_sign_category
      : "unclear";
  const subject: PhotoSubject =
    report.photo_subject in PHOTO_SUBJECT_KEY ? report.photo_subject : "unclear";
  const scope: ScreeningScope =
    report.screening_scope in PHOTO_SCOPE_KEY ? report.screening_scope : "subject_unclear";
  const scopeReasons = stringList(report.scope_reasons);
  // A CLEAR photo whose subject was identified is not an "Unclear" outcome:
  // quality, subject and screening scope already say exactly what happened.
  // The generic sign chip therefore stays hidden for those photos, while a
  // genuinely unidentified photo (subject not clear) and a real leaf
  // close-up keep it — no case ever claims a sign it did not see.
  const hideCategory =
    report.photo_quality === "clear" && scope !== "leaf_screening_applicable";
  // Neutral notice only for a CLEAR photo: the photo is fine, it is simply
  // not a leaf close-up (never a red error, never a low-quality warning).
  // The ear/head case is skipped because the interpretation already carries
  // its plain-language scope explanation — showing both would say it twice.
  const showScopeNotice =
    report.photo_quality === "clear" &&
    scope !== "leaf_screening_applicable" &&
    subject !== "wheat_ear_or_head";
  const retake =
    typeof report.retake_guidance === "string" && report.retake_guidance.trim()
      ? report.retake_guidance
      : null;

  const sections: { label: string; items: string[]; modifier: string }[] = [
    {
      label: t("vision.report.visible"),
      items: stringList(report.what_is_visible),
      modifier: "photo-report__list--visible",
    },
    {
      label: t("vision.report.notVisible"),
      items: stringList(report.what_is_not_clearly_visible),
      modifier: "photo-report__list--notVisible",
    },
  ];
  const checks = stringList(report.field_checks);
  const expert = stringList(report.expert_review_signs);
  const interpretation = report.screening_interpretation.trim();

  return (
    <section className="data-panel photo-report" aria-label={t("vision.report.heading")}>
      <div className="data-panel__head">
        <p className="data-panel__title">{t("vision.report.heading")}</p>
        <span className={`badge photo-report__status photo-report__status--${PHOTO_STATUS_MODIFIER[status]}`}>
          {t(PHOTO_STATUS_KEY[status])}
        </span>
      </div>

      {hideCategory ? null : (
        <p className="photo-report__category">
          <span className={`chip photo-report__category-chip photo-report__category-chip--${category}`}>
            {t(PHOTO_CATEGORY_KEY[category])}
          </span>
        </p>
      )}

      {/* Ordered outcome for a farmer: can it be read, what does it show,
          and does leaf screening apply — three plain facts, no jargon. */}
      <dl className="data-panel__grid photo-report__meta">
        <Row
          label={t("vision.report.quality")}
          value={t(PHOTO_STATUS_KEY[status])}
          ltr={false}
        />
        <Row
          label={t("vision.report.subject")}
          value={t(PHOTO_SUBJECT_KEY[subject])}
          ltr={false}
        />
        <Row
          label={t("vision.report.scopeShort")}
          value={t(PHOTO_SCOPE_SHORT_KEY[scope])}
          ltr={false}
        />
      </dl>

      {/* Model-side reasoning stays collapsed: machine context for audit,
          never the primary farmer-facing copy. */}
      {scopeReasons.length > 0 ? (
        <details className="agent-details agent-details--technical">
          <summary>{t("agent.technicalDetails")}</summary>
          <p className="card__meta">
            {t("vision.report.scope")}: {t(PHOTO_SCOPE_KEY[scope])}
          </p>
          <ul className="photo-report__scope-reasons">
            {scopeReasons.map((reason, index) => (
              <li key={index}>
                <BackendText text={reason} />
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {showScopeNotice ? (
        <p className="photo-report__scope-notice">{t(SCOPE_NOTICE_KEY[subject])}</p>
      ) : null}

      {sections.map((section) =>
        section.items.length > 0 ? (
          <div className="crop-evidence" key={section.label}>
            <p className="crop-evidence__label">{section.label}</p>
            <ul className={`crop-evidence__list ${section.modifier}`}>
              {section.items.map((item, index) => (
                <li key={index}>
                  <BackendText text={item} />
                </li>
              ))}
            </ul>
          </div>
        ) : null,
      )}

      {interpretation ? (
        <div className="crop-evidence">
          <p className="crop-evidence__label">{t("vision.report.interpretation")}</p>
          <ul className="crop-evidence__list photo-report__list--interpretation">
            <li>
              <BackendText text={interpretation} />
            </li>
          </ul>
        </div>
      ) : null}

      {checks.length > 0 ? (
        <div className="crop-evidence">
          <p className="crop-evidence__label">{t("vision.report.fieldChecks")}</p>
          <ul className="crop-evidence__list photo-report__list--checks">
            {checks.map((item, index) => (
              <li key={index}>
                <BackendText text={item} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {retake ? (
        <div className="crop-evidence">
          <p className="crop-evidence__label">{t("vision.report.retake")}</p>
          <ul className="crop-evidence__list photo-report__list--retake">
            <li>
              <BackendText text={retake} />
            </li>
          </ul>
        </div>
      ) : null}

      {expert.length > 0 ? (
        <div className="crop-evidence">
          <p className="crop-evidence__label">{t("vision.report.expert")}</p>
          <ul className="crop-evidence__list photo-report__list--expert">
            {expert.map((item, index) => (
              <li key={index}>
                <BackendText text={item} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

/* --------------------------------------------------------- input recap */

/**
 * "Your reported field information": the intake echoed back, one row at a
 * time. A row exists only for a key the backend actually returned, so an
 * unanswered field simply has no row — nothing here is defaulted, inferred or
 * verified. "Not sure" appears only where the farmer chose it, dates and
 * counts stay LTR inside the RTL Urdu layout, and localized choice values
 * follow the UI language. The heading and note state plainly that this is
 * farmer-reported or farmer-selected information.
 */
export function InputRecap({ recap }: { recap: InputRecap | null | undefined }) {
  const { t, tx } = useI18n();

  const asText = (value: unknown): string | null =>
    typeof value === "string" && value.trim() !== "" ? value.trim() : null;
  const asCodes = (value: unknown): string[] =>
    Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string" && item !== "")
      : [];

  const rows: { label: string; value: string; ltr: boolean }[] = [];
  const pushChoice = (label: string, prefix: string, raw: string | null) => {
    if (raw) rows.push({ label, value: tx(`${prefix}.${raw}`, raw), ltr: false });
  };

  pushChoice(t("recap.crop"), "crop", asText(recap?.crop));
  pushChoice(t("recap.area"), "area", asText(recap?.area_code));
  pushChoice(t("recap.growthStage"), "stage", asText(recap?.growth_stage));
  pushChoice(t("recap.soilMoisture"), "moisture", asText(recap?.soil_moisture));
  pushChoice(t("recap.drainage"), "drainage", asText(recap?.drainage));
  pushChoice(t("recap.onset"), "onset", asText(recap?.symptom_onset));
  pushChoice(t("recap.spreading"), "spreading", asText(recap?.symptoms_spreading));

  const observed = asText(recap?.observed_at);
  if (observed) rows.push({ label: t("recap.observedAt"), value: observed, ltr: true });

  const lastIrrigation = asText(recap?.last_irrigation_date);
  const irrigationHistory = asText(recap?.irrigation_history);
  if (lastIrrigation) {
    rows.push({ label: t("recap.lastIrrigation"), value: lastIrrigation, ltr: true });
  } else if (irrigationHistory) {
    // The farmer's own explicit unknown — shown as such, never as a default.
    rows.push({
      label: t("recap.lastIrrigation"),
      value: t("common.notSure"),
      ltr: false,
    });
  }

  const symptoms = asCodes(recap?.symptoms);
  if (symptoms.length > 0) {
    rows.push({
      label: t("recap.symptoms"),
      value: symptoms.map((code) => tx(`symptom.${code}`, code)).join(" · "),
      ltr: false,
    });
  }

  const photoCount = recap?.photo_count;
  if (typeof photoCount === "number") {
    rows.push({ label: t("recap.photos"), value: String(photoCount), ltr: true });
  }

  const views = asCodes(recap?.photo_views);
  if (views.length > 0) {
    rows.push({
      label: t("recap.photoViews"),
      value: views.map((code) => tx(`view.${code}`, code)).join(" · "),
      ltr: false,
    });
  }

  if (rows.length === 0) return null;

  return (
    <section className="data-panel input-recap" aria-label={t("recap.title")}>
      <div className="data-panel__head">
        <p className="data-panel__title">{t("recap.title")}</p>
      </div>
      <p className="input-recap__note">{t("recap.note")}</p>
      <dl className="data-panel__grid input-recap__grid">
        {rows.map((row) => (
          <Row
            key={`${row.label}:${row.value}`}
            label={row.label}
            value={row.value}
            ltr={row.ltr}
          />
        ))}
      </dl>
    </section>
  );
}

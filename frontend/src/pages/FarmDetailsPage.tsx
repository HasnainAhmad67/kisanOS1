import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, createAssessment } from "../api/client";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import {
  Choice,
  ChoiceGroup,
  SelectField,
  TextareaField,
  TextInput,
} from "../components/FormField";
import { useAssessment } from "../hooks/useAssessment";
import { useConfig } from "../hooks/useConfig";
import { translate, useI18n } from "../i18n";
import type { AssessmentCreatePayload, IrrigationHistory } from "../types/backend";

/** Literal expected by backend config.py (`consent_version` default). */
const CONSENT_VERSION = "2026-10-03-gemini-v1";
const TIMEZONE = "Asia/Karachi";

/**
 * Built-in Bahawalpur pilot-area fallback. Used whenever the live config
 * request fails, takes too long, or returns an empty area list, so the Area
 * dropdown is always usable (select-only, never free text). Live config
 * areas always take priority when available.
 */
const FALLBACK_AREAS: { value: string; label: string }[] = [
  { value: "bahawalpur_city", label: "Bahawalpur City" },
  { value: "ahmadpur_east", label: "Ahmedpur East" },
  { value: "hasilpur", label: "Hasilpur" },
  { value: "khairpur_tamewali", label: "Khairpur Tamewali" },
  { value: "yazman", label: "Yazman" },
  { value: "chishtian", label: "Chishtian" },
  { value: "haroonabad", label: "Haroonabad" },
  { value: "fort_abbas", label: "Fort Abbas" },
];

/**
 * Fallback slug -> area code accepted by POST /assessments (the backend's
 * configured AREAS). Slugs that are already valid codes pass through
 * unchanged, so "Continue to photos" works exactly as with live config.
 */
const FALLBACK_AREA_CODES: Record<string, string> = {
  bahawalpur_city: "bahawalpur_sadar",
  chishtian: "bahawalpur_sadar",
  haroonabad: "bahawalpur_sadar",
  fort_abbas: "bahawalpur_sadar",
};

/** How long the live config may load before the saved list takes over. */
const CONFIG_FALLBACK_MS = 3000;

const STAGE_ORDER = [
  "emergence",
  "cri",
  "tillering",
  "jointing",
  "booting",
  "heading",
  "flowering",
  "milk",
  "dough",
  "maturity",
] as const;

const SYMPTOM_CHIPS = [
  { value: "yellowing", key: "symptom.yellowing" },
  { value: "spots", key: "symptom.spots" },
  { value: "wilting", key: "symptom.wilting" },
  { value: "rust_like", key: "symptom.rust_like" },
  { value: "drying", key: "symptom.drying" },
  { value: "insects", key: "symptom.insects" },
] as const;

/**
 * Farm details form — POST /api/v1/assessments. On success the
 * assessment id + access token move into the session (sessionStorage)
 * and the flow continues to photo upload.
 */
export function FarmDetailsPage() {
  const navigate = useNavigate();
  const { startAssessment } = useAssessment();
  const { config, error: configError, loading: configLoading } = useConfig();
  const { t, locale } = useI18n();

  const [irrigation, setIrrigation] = useState<IrrigationHistory>("not_sure");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [symptomError, setSymptomError] = useState<string | null>(null);
  const [configTimedOut, setConfigTimedOut] = useState(false);

  // Safety net: if the live config request hangs too long, stop waiting on it.
  useEffect(() => {
    if (!configLoading) return;
    const timer = window.setTimeout(() => setConfigTimedOut(true), CONFIG_FALLBACK_MS);
    return () => window.clearTimeout(timer);
  }, [configLoading]);

  // Live API areas always take priority; the saved list is used only when the
  // request failed, took too long, or returned no areas.
  const liveAreas = config?.supported_areas?.length
    ? config.supported_areas.map((area) => ({ value: area.code, label: area.name }))
    : null;
  const usingFallback =
    !liveAreas && (Boolean(configError) || configTimedOut || !configLoading);
  const areaOptions = liveAreas ?? (usingFallback ? FALLBACK_AREAS : []);

  const stageOptions = [
    ...STAGE_ORDER.map((value) => ({
      value: value as string,
      label: translate(locale, `stage.${value}` as `stage.${typeof value}`),
    })),
    { value: "not_sure", label: t("common.notSure") },
  ];

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setSymptomError(null);

    const form = event.currentTarget;
    const data = new FormData(form);

    const symptoms = data
      .getAll("symptoms")
      .map((value) => String(value))
      .filter(Boolean);
    if (symptoms.length === 0) {
      setSymptomError(t("farm.symptomsError"));
      return;
    }
    if (!data.get("area_code")) {
      setFormError(t("farm.areaError"));
      return;
    }

    const rawArea = String(data.get("area_code") ?? "");
    const payload: AssessmentCreatePayload = {
      crop: "wheat",
      crop_confirmed: data.get("crop_confirmed") === "on",
      // Fallback slugs are translated to the backend's accepted area code so
      // submission works exactly as with live config; live codes pass through.
      area_code: (FALLBACK_AREA_CODES[rawArea] ??
        rawArea) as AssessmentCreatePayload["area_code"],
      area_confirmed: data.get("area_confirmed") === "on",
      growth_stage: (data.get("growth_stage") ??
        "not_sure") as AssessmentCreatePayload["growth_stage"],
      irrigation_history: data.get(
        "irrigation_history",
      ) as IrrigationHistory,
      last_irrigation_date:
        irrigation === "known"
          ? String(data.get("last_irrigation_date") ?? "")
          : null,
      soil_texture: (data.get("soil_texture") ??
        "not_sure") as AssessmentCreatePayload["soil_texture"],
      soil_moisture: (data.get("soil_moisture") ??
        "not_sure") as AssessmentCreatePayload["soil_moisture"],
      drainage: (data.get("drainage") ??
        "not_sure") as AssessmentCreatePayload["drainage"],
      symptom_onset: (data.get("symptom_onset") ??
        "not_sure") as AssessmentCreatePayload["symptom_onset"],
      symptoms_spreading: (data.get("symptoms_spreading") ??
        "not_sure") as AssessmentCreatePayload["symptoms_spreading"],
      symptoms,
      notes: String(data.get("notes") ?? "").trim() || null,
      locale,
      timezone: TIMEZONE,
      consent_given: data.get("consent_given") === "on",
      consent_version: CONSENT_VERSION,
      gemini_explanation_consent: data.get("gemini_explanation_consent") === "on",
    };

    if (payload.irrigation_history === "known" && !payload.last_irrigation_date) {
      setFormError(t("farm.dateError"));
      return;
    }

    setSubmitting(true);
    try {
      const created = await createAssessment(payload);
      startAssessment(created, payload);
      navigate("/photos");
    } catch (cause) {
      if (cause instanceof ApiError) {
        setFormError(
          `${cause.message}${cause.requestId ? ` (request ${cause.requestId})` : ""}`,
        );
      } else {
        setFormError(t("farm.saveError"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page page--farm stack">
      <img
        className="page-tex"
        src="/images/soil-texture.jpg"
        alt=""
        loading="lazy"
        decoding="async"
        aria-hidden="true"
      />
      <h1 className="page-title">
        {t("farm.title")}
        {locale === "ur" ? (
          <span className="label-en" dir="ltr">
            {translate("en", "farm.title")}
          </span>
        ) : null}
      </h1>
      <p className="page-intro">{t("farm.intro")}</p>

      {formError ? <Alert>{formError}</Alert> : null}
      {usingFallback ? <Alert>{t("farm.configWarn")}</Alert> : null}

      <form onSubmit={handleSubmit} className="farm-form">
        <ChoiceGroup legend={t("farm.cropLegend")} hint={t("farm.cropHint")}>
          <Choice
            type="checkbox"
            name="crop_confirmed"
            required
            label={t("farm.cropConfirm")}
          />
        </ChoiceGroup>

        <SelectField
          label={t("farm.areaLabel")}
          name="area_code"
          required
          placeholder={
            configLoading && !usingFallback
              ? t("farm.areaLoading")
              : t("farm.areaPlaceholder")
          }
          options={areaOptions}
        />
        <ChoiceGroup legend={t("farm.areaConfirmLegend")}>
          <Choice
            type="checkbox"
            name="area_confirmed"
            required
            label={t("farm.areaConfirm")}
          />
        </ChoiceGroup>

        <SelectField
          label={t("farm.growthLabel")}
          name="growth_stage"
          options={stageOptions}
          defaultValue="not_sure"
        />

        <SelectField
          label={t("farm.irrigationLabel")}
          name="irrigation_history"
          required
          options={[
            { value: "known", label: t("common.known") },
            { value: "not_sure", label: t("common.notSure") },
          ]}
          value={irrigation}
          onChange={(event) =>
            setIrrigation(event.target.value as IrrigationHistory)
          }
        />
        {irrigation === "known" ? (
          <TextInput
            label={t("farm.lastIrrigation")}
            name="last_irrigation_date"
            type="date"
            required
          />
        ) : null}

        <SelectField
          label={t("farm.soilTexture")}
          name="soil_texture"
          options={[
            { value: "sandy", label: t("soil.sandy") },
            { value: "loamy", label: t("soil.loamy") },
            { value: "clayey", label: t("soil.clayey") },
            { value: "not_sure", label: t("common.notSure") },
          ]}
          defaultValue="not_sure"
        />
        <SelectField
          label={t("farm.soilMoisture")}
          name="soil_moisture"
          options={[
            { value: "dry", label: t("moisture.dry") },
            { value: "moist", label: t("moisture.moist") },
            { value: "wet", label: t("moisture.wet") },
            { value: "not_sure", label: t("common.notSure") },
          ]}
          defaultValue="not_sure"
        />
        <SelectField
          label={t("farm.drainage")}
          name="drainage"
          options={[
            { value: "good", label: t("drainage.good") },
            { value: "poor", label: t("drainage.poor") },
            { value: "waterlogging", label: t("drainage.waterlogging") },
            { value: "not_sure", label: t("common.notSure") },
          ]}
          defaultValue="not_sure"
        />

        <SelectField
          label={t("farm.onsetLabel")}
          name="symptom_onset"
          options={[
            { value: "today", label: t("onset.today") },
            { value: "recent", label: t("onset.recent") },
            { value: "over_a_week", label: t("onset.over_a_week") },
            { value: "not_sure", label: t("onset.not_sure") },
          ]}
          defaultValue="not_sure"
        />

        <ChoiceGroup legend={t("farm.spreadingLegend")} columns>
          {(
            [
              { value: "yes", key: "spreading.yes" },
              { value: "no", key: "spreading.no" },
              { value: "not_sure", key: "spreading.not_sure" },
            ] as const
          ).map((option) => (
            <Choice
              key={option.value}
              type="radio"
              name="symptoms_spreading"
              value={option.value}
              required
              defaultChecked={option.value === "not_sure"}
              label={t(option.key)}
            />
          ))}
        </ChoiceGroup>

        <ChoiceGroup
          legend={t("farm.symptomsLegend")}
          hint={t("farm.symptomsHint")}
          columns
        >
          {SYMPTOM_CHIPS.map((chip) => (
            <Choice
              key={chip.value}
              type="checkbox"
              name="symptoms"
              value={chip.value}
              label={t(chip.key)}
            />
          ))}
        </ChoiceGroup>
        {symptomError ? <Alert>{symptomError}</Alert> : null}

        <TextareaField
          label={t("farm.notesLabel")}
          name="notes"
          hint={t("farm.notesHint")}
          maxLength={1500}
        />

        <ChoiceGroup legend={t("farm.privacyLegend")} hint={t("farm.privacyHint")}>
          <Choice
            type="checkbox"
            name="consent_given"
            required
            label={t("farm.consent")}
          />
          <Choice
            type="checkbox"
            name="gemini_explanation_consent"
            label={t("farm.geminiConsent")}
          />
        </ChoiceGroup>

        <div className="stack" style={{ marginBlockStart: "var(--space-5)" }}>
          <Button type="submit" block disabled={submitting || configLoading}>
            {submitting ? t("farm.saving") : t("farm.submit")}
          </Button>
          <LinkButton to="/" variant="secondary" block>
            {t("common.back")}
          </LinkButton>
        </div>
      </form>
    </div>
  );
}

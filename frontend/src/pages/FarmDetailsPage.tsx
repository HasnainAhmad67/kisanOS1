import { useState, type FormEvent } from "react";
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
import { useLocale } from "../hooks/useLocale";
import type { AssessmentCreatePayload, IrrigationHistory } from "../types/backend";

/** Literal expected by backend config.py (`consent_version` default). */
const CONSENT_VERSION = "2026-10-03-gemini-v1";
const TIMEZONE = "Asia/Karachi";

const GROWTH_STAGES = [
  { value: "emergence", label: "Emergence" },
  { value: "cri", label: "Crown root initiation (CRI)" },
  { value: "tillering", label: "Tillering" },
  { value: "jointing", label: "Jointing" },
  { value: "booting", label: "Booting" },
  { value: "heading", label: "Heading" },
  { value: "flowering", label: "Flowering" },
  { value: "milk", label: "Milk" },
  { value: "dough", label: "Dough" },
  { value: "maturity", label: "Maturity" },
  { value: "not_sure", label: "Not sure" },
];

const SYMPTOM_CHIPS = [
  { value: "yellowing", label: "Yellowing" },
  { value: "spots", label: "Spots" },
  { value: "wilting", label: "Wilting" },
  { value: "rust_like", label: "Rust-like marks" },
  { value: "drying", label: "Drying" },
  { value: "insects", label: "Insects visible" },
];

/**
 * Farm details form — POST /api/v1/assessments. On success the
 * assessment id + access token move into the session (sessionStorage)
 * and the flow continues to photo upload.
 */
export function FarmDetailsPage() {
  const navigate = useNavigate();
  const { startAssessment } = useAssessment();
  const { config, error: configError, loading: configLoading } = useConfig();
  const { locale } = useLocale();

  const [irrigation, setIrrigation] = useState<IrrigationHistory>("not_sure");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [symptomError, setSymptomError] = useState<string | null>(null);

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
      setSymptomError("Select at least one symptom you can see.");
      return;
    }
    if (!data.get("area_code")) {
      setFormError("Select your pilot area.");
      return;
    }

    const payload: AssessmentCreatePayload = {
      crop: "wheat",
      crop_confirmed: data.get("crop_confirmed") === "on",
      area_code: data.get("area_code") as AssessmentCreatePayload["area_code"],
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
      setFormError("Enter the last irrigation date, or choose “Not sure”.");
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
        setFormError("Something went wrong saving the assessment. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <h1>
        Farm ki Tafseel
        <span className="label-en">Farm details</span>
      </h1>
      <p className="page-intro">
        Fields marked <span className="field__required">*</span> are required.
        Everything else can be “not sure”.
      </p>

      {formError ? <Alert>{formError}</Alert> : null}
      {configError ? (
        <Alert>
          Live configuration unavailable ({configError}) — area list may be
          out of date.
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit}>
        <ChoiceGroup legend="Crop" hint="The pilot supports wheat only.">
          <Choice
            type="checkbox"
            name="crop_confirmed"
            required
            label="I confirm this field is wheat (گندم)"
          />
        </ChoiceGroup>

        <SelectField
          label="Area"
          name="area_code"
          required
          placeholder={
            configLoading ? "Loading areas…" : "Select your pilot area"
          }
          options={
            config
              ? config.supported_areas.map((area) => ({
                  value: area.code,
                  label: area.name,
                }))
              : []
          }
        />
        <ChoiceGroup legend="Area confirmation">
          <Choice
            type="checkbox"
            name="area_confirmed"
            required
            label="I confirm this Bahawalpur pilot area"
          />
        </ChoiceGroup>

        <SelectField
          label="Growth stage"
          name="growth_stage"
          options={GROWTH_STAGES}
          defaultValue="not_sure"
        />

        <SelectField
          label="Irrigation history"
          name="irrigation_history"
          required
          options={[
            { value: "known", label: "Known" },
            { value: "not_sure", label: "Not sure" },
          ]}
          value={irrigation}
          onChange={(event) =>
            setIrrigation(event.target.value as IrrigationHistory)
          }
        />
        {irrigation === "known" ? (
          <TextInput
            label="Last irrigation date"
            name="last_irrigation_date"
            type="date"
            required
          />
        ) : null}

        <SelectField
          label="Soil texture"
          name="soil_texture"
          options={[
            { value: "sandy", label: "Sandy" },
            { value: "loamy", label: "Loamy" },
            { value: "clayey", label: "Clayey" },
            { value: "not_sure", label: "Not sure" },
          ]}
          defaultValue="not_sure"
        />
        <SelectField
          label="Soil moisture (by hand)"
          name="soil_moisture"
          options={[
            { value: "dry", label: "Dry" },
            { value: "moist", label: "Moist" },
            { value: "wet", label: "Wet" },
            { value: "not_sure", label: "Not sure" },
          ]}
          defaultValue="not_sure"
        />
        <SelectField
          label="Drainage"
          name="drainage"
          options={[
            { value: "good", label: "Good" },
            { value: "poor", label: "Poor" },
            { value: "waterlogging", label: "Waterlogging" },
            { value: "not_sure", label: "Not sure" },
          ]}
          defaultValue="not_sure"
        />

        <SelectField
          label="When did symptoms start?"
          name="symptom_onset"
          options={[
            { value: "today", label: "Today" },
            { value: "recent", label: "Within the last few days" },
            { value: "over_a_week", label: "Over a week ago" },
            { value: "not_sure", label: "Not sure" },
          ]}
          defaultValue="not_sure"
        />

        <ChoiceGroup legend="Are symptoms spreading?" columns>
          {(
            [
              { value: "yes", label: "Yes" },
              { value: "no", label: "No" },
              { value: "not_sure", label: "Not sure" },
            ] as const
          ).map((option) => (
            <Choice
              key={option.value}
              type="radio"
              name="symptoms_spreading"
              value={option.value}
              required
              defaultChecked={option.value === "not_sure"}
              label={option.label}
            />
          ))}
        </ChoiceGroup>

        <ChoiceGroup
          legend="Symptoms you can see"
          hint="Select at least one."
          columns
        >
          {SYMPTOM_CHIPS.map((chip) => (
            <Choice
              key={chip.value}
              type="checkbox"
              name="symptoms"
              value={chip.value}
              label={chip.label}
            />
          ))}
        </ChoiceGroup>
        {symptomError ? <Alert>{symptomError}</Alert> : null}

        <TextareaField
          label="Notes"
          name="notes"
          hint="Up to 1500 characters. Optional."
          maxLength={1500}
        />

        <ChoiceGroup
          legend="Privacy"
          hint="Consent is required to save an assessment. GPS coordinates are not collected."
        >
          <Choice
            type="checkbox"
            name="consent_given"
            required
            label="I agree to save this assessment and its photos for my own use"
          />
          <Choice
            type="checkbox"
            name="gemini_explanation_consent"
            label="Add the optional AI explanation (sends text — never photos — to Gemini)"
          />
        </ChoiceGroup>

        <div className="stack" style={{ marginBlockStart: "var(--space-5)" }}>
          <Button type="submit" block disabled={submitting || configLoading}>
            {submitting
              ? "Saving…"
              : "Photo Upload Karein — Continue to photos"}
          </Button>
          <LinkButton to="/" variant="secondary" block>
            Back
          </LinkButton>
        </div>
      </form>
    </div>
  );
}

import { useState, type FormEvent } from "react";
import { ApiError, addFollowup } from "../api/client";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { Choice, ChoiceGroup, TextareaField } from "../components/FormField";
import { useAssessment } from "../hooks/useAssessment";
import { translate, useI18n } from "../i18n";
import type { ConsentCompletion, FollowUpCreated } from "../types/backend";

/** POST /assessments/{id}/followups — a timestamped farmer observation. */
export function FollowupPage() {
  const { assessment } = useAssessment();
  const { t, locale } = useI18n();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<FollowUpCreated | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assessment) return;
    setError(null);

    const form = event.currentTarget; // capture before await (currentTarget nulls)
    const data = new FormData(form);
    const note = String(data.get("note") ?? "").trim();
    if (note.length < 1) {
      setError(t("fu.noteError"));
      return;
    }
    const completion = String(
      data.get("completion") ?? "not_sure",
    ) as ConsentCompletion;

    setSaving(true);
    try {
      const created = await addFollowup(
        assessment.assessmentId,
        assessment.accessToken,
        { note, completion },
      );
      setSaved(created);
      form.reset();
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : t("fu.saveError"),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page page--followup stack">
      <h1 className="page-title">
        {t("fu.title")}
        {locale === "ur" ? (
          <span className="label-en" dir="ltr">
            {translate("en", "fu.title")}
          </span>
        ) : null}
      </h1>
      <p className="page-intro">{t("fu.intro")}</p>

      {error ? <Alert>{error}</Alert> : null}
      {saved ? <Alert tone="success">{saved.message}</Alert> : null}

      <Card title={t("fu.cardTitle")}>
        <form onSubmit={handleSubmit}>
          <TextareaField
            label={t("fu.noteLabel")}
            name="note"
            hint={t("fu.noteHint")}
            required
            maxLength={1500}
          />

          <ChoiceGroup legend={t("fu.completionLegend")} columns>
            {(
              [
                { value: "completed", key: "fu.completed" },
                { value: "partially_completed", key: "fu.partially" },
                { value: "not_completed", key: "fu.notCompleted" },
                { value: "not_sure", key: "common.notSure" },
              ] as const
            ).map((option) => (
              <Choice
                key={option.value}
                type="radio"
                name="completion"
                value={option.value}
                defaultChecked={option.value === "not_sure"}
                label={t(option.key)}
              />
            ))}
          </ChoiceGroup>

          <Button type="submit" block disabled={saving}>
            {saving ? t("fu.saving") : t("fu.save")}
          </Button>
        </form>
      </Card>

      <div className="stack">
        <LinkButton to="/results" variant="secondary" block>
          {t("fu.back")}
        </LinkButton>
      </div>
    </div>
  );
}

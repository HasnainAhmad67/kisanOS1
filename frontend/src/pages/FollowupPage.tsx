import { useState, type FormEvent } from "react";
import { ApiError, addFollowup } from "../api/client";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { Choice, ChoiceGroup, TextareaField } from "../components/FormField";
import { useAssessment } from "../hooks/useAssessment";
import type { ConsentCompletion, FollowUpCreated } from "../types/backend";

/** POST /assessments/{id}/followups — a timestamped farmer observation. */
export function FollowupPage() {
  const { assessment } = useAssessment();
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
    if (!note) {
      setError("Write what you observed.");
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
        cause instanceof ApiError
          ? cause.message
          : "Could not save the follow-up.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <h1>Follow-up</h1>
      <p className="page-intro">
        A follow-up saves a new timestamped observation. It never proves that
        a condition progressed or healed.
      </p>

      {error ? <Alert>{error}</Alert> : null}
      {saved ? (
        <Alert tone="success">{saved.message}</Alert>
      ) : null}

      <Card title="What did you observe?">
        <form onSubmit={handleSubmit}>
          <TextareaField
            label="Observation"
            name="note"
            hint="1–1500 characters. Say what changed since the last check."
            required
            maxLength={1500}
          />

          <ChoiceGroup legend="Did you complete the checks?" columns>
            {(
              [
                { value: "completed", label: "Completed" },
                { value: "partially_completed", label: "Partially" },
                { value: "not_completed", label: "Not completed" },
                { value: "not_sure", label: "Not sure" },
              ] as const
            ).map((option) => (
              <Choice
                key={option.value}
                type="radio"
                name="completion"
                value={option.value}
                defaultChecked={option.value === "not_sure"}
                label={option.label}
              />
            ))}
          </ChoiceGroup>

          <Button type="submit" block disabled={saving}>
            {saving ? "Saving…" : "Save follow-up"}
          </Button>
        </form>
      </Card>

      <div className="stack">
        <LinkButton to="/results" variant="secondary" block>
          Back to results
        </LinkButton>
      </div>
    </div>
  );
}

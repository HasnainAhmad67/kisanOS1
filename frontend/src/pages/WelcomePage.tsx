import { LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { useConfig } from "../hooks/useConfig";

export function WelcomePage() {
  const { config, error, loading } = useConfig();

  return (
    <div className="stack">
      <h1>New field check</h1>
      <p className="page-intro">
        Tell us what you are seeing in your wheat field, add a couple of
        photos, and get a short plan of what to check next — in a few minutes.
      </p>

      <Card title="How it works">
        <ol className="agent-card__list">
          <li>Answer a few questions about your field.</li>
          <li>Take close-up photos of the affected leaves.</li>
          <li>
            Review the five agent cards (weather, water, crop, vision, market)
            and your farm plan.
          </li>
        </ol>
      </Card>

      <Card tone="safety" title="Safety notice">
        {config ? (
          <p style={{ margin: 0 }}>{config.safety_notice}</p>
        ) : loading ? (
          <p className="empty-note">Loading live configuration…</p>
        ) : (
          <p className="empty-note">
            Live configuration unavailable{error ? ` (${error})` : ""}.
          </p>
        )}
      </Card>

      {config ? (
        <p className="card__meta">
          Crop: {config.supported_crop} · Pilot areas:{" "}
          {config.supported_areas.map((area) => area.name).join(", ")}
        </p>
      ) : null}

      <div className="row">
        <LinkButton to="/farm-details">Start a new check</LinkButton>
      </div>
    </div>
  );
}

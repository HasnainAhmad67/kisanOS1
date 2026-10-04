import { StatusBadge } from "./StatusBadge";
import type { AgentId, AgentResult } from "../types/backend";

const TITLES: Record<AgentId, string> = {
  weather: "Weather",
  water: "Water",
  crop: "Crop",
  vision: "Vision (photo)",
  market: "Market",
};

/** Presentation icons — decorative only (screen readers get the title). */
const ICONS: Record<AgentId, string> = {
  weather: "☁️",
  water: "💧",
  crop: "🌱",
  vision: "👁️",
  market: "💰",
};

interface AgentCardProps {
  agentId: AgentId;
  /** Present once results are loaded; undefined keeps the shell placeholder. */
  result?: AgentResult | null;
}

export function AgentCard({ agentId, result }: AgentCardProps) {
  return (
    <section
      className={`card agent-card agent-card--${agentId}`}
      aria-labelledby={`agent-${agentId}`}
    >
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3 id={`agent-${agentId}`} style={{ margin: 0 }}>
          <span className="agent-card__icon" aria-hidden="true">
            {ICONS[agentId]}
          </span>
          {TITLES[agentId]}
        </h3>
        <StatusBadge status={result?.status ?? "pending"} />
      </div>
      {result ? (
        <>
          <p className="agent-card__summary">{result.summary}</p>
          {result.observations.length > 0 ? (
            <ul className="agent-card__list">
              {result.observations.slice(0, 5).map((observation) => (
                <li key={observation}>{observation}</li>
              ))}
            </ul>
          ) : null}
          {result.checks.length > 0 ? (
            <>
              <p className="card__meta" style={{ marginBlockStart: "var(--space-3)" }}>
                Field checks
              </p>
              <ul className="agent-card__list">
                {result.checks.slice(0, 3).map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            </>
          ) : null}
          <p className="card__meta">
            Evidence: {result.evidence_band.replace(/_/g, " ")}
            {result.evidence_reason ? ` — ${result.evidence_reason}` : ""}
          </p>
          {result.sources.length > 0 ? (
            <ul className="source-list">
              {result.sources.map((source) => (
                <li key={`${source.title}-${source.publisher}`}>
                  {source.url ? (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      {source.title}
                    </a>
                  ) : (
                    <span>{source.title}</span>
                  )}{" "}
                  <span className="card__meta">
                    — {source.publisher} · {source.source_status.replace(/_/g, " ")}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          {result.safety_flags.length > 0 ? (
            <ul className="agent-card__list safety-flags">
              {result.safety_flags.map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
            </ul>
          ) : null}
          <p className="card__meta">
            {new Date(result.created_at).toLocaleString()} ·{" "}
            {result.provider_or_model}
          </p>
        </>
      ) : (
        <p className="empty-note">
          🌾 Nothing from this agent yet — no data has been returned for this
          check, so nothing is shown.
        </p>
      )}
    </section>
  );
}

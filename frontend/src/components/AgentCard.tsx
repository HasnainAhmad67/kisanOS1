import { StatusBadge } from "./StatusBadge";
import { translate, useI18n } from "../i18n";
import type { AgentId, AgentResult } from "../types/backend";

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

/**
 * One agent result card. Summary, observations and checks stay visible;
 * evidence band + sources + provenance collapse behind a native
 * <details> (accessible, keyboard operable). Safety flags never hide.
 */
export function AgentCard({ agentId, result }: AgentCardProps) {
  const { t, locale } = useI18n();
  const title = translate(locale, `agent.${agentId}` as `agent.${typeof agentId}`);

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
          {title}
        </h3>
        <StatusBadge status={result?.status ?? "pending"} />
      </div>
      {result ? (
        <>
          <p className="agent-card__summary">{result.summary}</p>
          {agentId === "vision" && result.safety_flags.includes("low_quality_image") ? (
            <p className="vision-notice vision-notice--warn">
              <strong>⚠️ {t("vision.soft.title")}</strong>
              <br />
              {t("vision.soft.hint")}
            </p>
          ) : null}
          {agentId === "vision" && result.safety_flags.includes("photo_quality_failed") ? (
            <p className="vision-notice vision-notice--blocked">
              <strong>🚫 {t("vision.blocked.title")}</strong>
              <br />
              {t("vision.blocked.hint")}
            </p>
          ) : null}
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
                {t("agent.fieldChecks")}
              </p>
              <ul className="agent-card__list">
                {result.checks.slice(0, 3).map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            </>
          ) : null}

          {result.safety_flags.length > 0 ? (
            <ul className="agent-card__list safety-flags">
              {result.safety_flags.map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
            </ul>
          ) : null}

          {/* Evidence + sources + provenance — collapsible, never hidden content */}
          <details className="agent-details">
            <summary>{t("agent.evidenceSources")}</summary>
            <p className="card__meta">
              {t("agent.evidence")} {result.evidence_band.replace(/_/g, " ")}
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
                      — {source.publisher} ·{" "}
                      {source.source_status.replace(/_/g, " ")}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="card__meta">
              <time className="num" dateTime={result.created_at}>
                {new Date(result.created_at).toLocaleString()}
              </time>{" "}
              · {result.provider_or_model}
            </p>
          </details>
        </>
      ) : (
        <p className="empty-note">🌾 {t("agent.empty")}</p>
      )}
    </section>
  );
}

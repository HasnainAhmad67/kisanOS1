import { BackendText } from "./BackendText";
import { MarketQuote, isAmisQuote } from "./MarketQuote";
import {
  CropEvidencePanel,
  FieldInformation,
  PhotoScreeningReport,
  WaterNextInformation,
  WeatherPanel,
  isCropCardData,
  isVisionPhotoReport,
  isWaterCardData,
  isWeatherCardData,
} from "./ResultPanels";
import { StatusBadge } from "./StatusBadge";
import { translate, useI18n, type Locale } from "../i18n";
import type { AgentId, AgentResult } from "../types/backend";

/** Presentation icons — decorative only (screen readers get the title). */
const ICONS: Record<AgentId, string> = {
  weather: "☁️",
  water: "💧",
  crop: "🌱",
  vision: "👁️",
  market: "💰",
};

/**
 * Look up a dynamic backend token (evidence band, source status, safety
 * flag). English keeps the raw rendering it always had; Urdu uses the
 * translated dictionary value, falling back to a readable English token.
 */
function txToken(
  tx: (key: string, fallback: string) => string,
  locale: Locale,
  prefix: string,
  raw: string,
): string {
  return tx(`${prefix}.${raw}`, locale === "ur" ? raw.replace(/_/g, " ") : raw);
}

interface AgentCardProps {
  agentId: AgentId;
  /** Present once results are loaded; undefined keeps the shell placeholder. */
  result?: AgentResult | null;
}

/**
 * One agent result card. Summary, observations and checks stay visible;
 * evidence band + sources + provenance collapse behind a native <details>
 * (accessible, keyboard operable), and safety flags move into a collapsed
 * "Technical details" section — machine-facing context, never guidance.
 *
 * The Crop evidence split, the Water "what is needed next" panel and the
 * Vision photo screening report take over the plain lists they already cover,
 * so no statement appears twice.
 *
 * UI language drives every label; backend prose is rendered through
 * <BackendText> (Urdu when a known wording exists, English under its own
 * label otherwise) so English UI output stays byte-for-byte unchanged.
 */
export function AgentCard({ agentId, result }: AgentCardProps) {
  const { t, tx, locale } = useI18n();
  const title = translate(locale, `agent.${agentId}` as `agent.${typeof agentId}`);
  /* Structured panels take over the plain lists they already cover, so a
     farmer never reads the same statement twice on one card. */
  const waterData =
    result && agentId === "water" && isWaterCardData(result.data) ? result.data : null;
  const cropData =
    result && agentId === "crop" && isCropCardData(result.data) ? result.data : null;
  /* Vision's structured photo screening report, when the gateway produced one. */
  const photoReport =
    result && agentId === "vision" && isVisionPhotoReport(result.data.photo_report)
      ? result.data.photo_report
      : null;
  /* True when the Water panel renders (and therefore owns the card's checks). */
  const waterOwnsChecks =
    waterData !== null &&
    Array.isArray(waterData.next_information_needed) &&
    waterData.next_information_needed.length > 0;

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
          <p className="agent-card__summary">
            <BackendText text={result.summary} />
          </p>
          {/* Vision photo screening report: whether the photo could be
              assessed, the visible-sign category, what the photo does and
              does not show, the preliminary interpretation, the next field
              checks, retake guidance and expert-review signs. */}
          {photoReport ? <PhotoScreeningReport report={photoReport} /> : null}
          {/* Structured provider values (Weather) and the field-completeness
              report (Water) — rendered only for the matching backend shape. */}
          {agentId === "weather" && isWeatherCardData(result.data) ? (
            <WeatherPanel data={result.data} sources={result.sources} />
          ) : null}
          {waterData ? (
            <>
              <FieldInformation data={waterData} />
              <WaterNextInformation data={waterData} checks={result.checks} />
            </>
          ) : null}
          {/* Crop evidence split: five headed sections replace the plain
              observation/check lists below so nothing is stated twice. */}
          {cropData ? <CropEvidencePanel data={cropData} checks={result.checks} /> : null}
          {/* Live mandi price: the localized unavailable notice, or the quote
              panel when Punjab AMIS returned a verified row. */}
          {agentId === "market" && result.status === "unavailable" ? (
            <p className="market-notice">{t("market.unavailable")}</p>
          ) : null}
          {agentId === "market" && isAmisQuote(result.data.quote) ? (
            <MarketQuote quote={result.data.quote} />
          ) : null}
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
          {/* Fallback states: an honest, non-blocking note so a missing or
              unavailable photo never reads as a failed analysis. No sign is
              claimed for a photo that was not assessed, and the other cards
              plus the Farm Plan are unaffected. */}
          {agentId === "vision" &&
          result.status === "not_assessed" &&
          !photoReport &&
          result.safety_flags.includes("manual_fallback_available") ? (
            <p className="vision-notice vision-notice--info">{t("vision.noPhoto.note")}</p>
          ) : null}
          {agentId === "vision" &&
          (result.status === "unavailable" ||
            result.safety_flags.includes("model_unavailable")) ? (
            <p className="vision-notice vision-notice--info">
              {t("vision.unavailable.note")}
            </p>
          ) : null}
          {/* The photo report replaces the raw observation/check lists: the
              report already carries what the photo shows and what to check
              next, in farmer wording and localized. */}
          {result.observations.length > 0 && !cropData && !photoReport ? (
            <ul className="agent-card__list">
              {result.observations.slice(0, 5).map((observation) => (
                <li key={observation}>
                  <BackendText text={observation} />
                </li>
              ))}
            </ul>
          ) : null}
          {result.checks.length > 0 && !cropData && !waterOwnsChecks && !photoReport ? (
            <>
              <p className="card__meta" style={{ marginBlockStart: "var(--space-3)" }}>
                {t("agent.fieldChecks")}
              </p>
              <ul className="agent-card__list">
                {result.checks.slice(0, 3).map((check) => (
                  <li key={check}>
                    <BackendText text={check} />
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {result.safety_flags.length > 0 ? (
            <details className="agent-details agent-details--technical">
              <summary>{t("agent.technicalDetails")}</summary>
              <p className="card__meta">{t("agent.safetyFlags")}</p>
              <ul className="agent-card__list safety-flags">
                {result.safety_flags.map((flag) => (
                  <li key={flag}>{txToken(tx, locale, "flag", flag)}</li>
                ))}
              </ul>
            </details>
          ) : null}

          {/* Evidence + sources + provenance — collapsible, never hidden content */}
          <details className="agent-details">
            <summary>{t("agent.evidenceSources")}</summary>
            <p className="card__meta">
              {t("agent.evidence")}{" "}
              {txToken(tx, locale, "ev.band", result.evidence_band)}
              {result.evidence_reason ? (
                <>
                  {" — "}
                  <BackendText text={result.evidence_reason} />
                </>
              ) : null}
            </p>
            {result.sources.length > 0 ? (
              <>
                {/* Heading only exists in Urdu mode — English markup is untouched. */}
                {locale === "ur" ? (
                  <p className="card__meta">{t("agent.sources")}</p>
                ) : null}
                <ul className="source-list">
                  {result.sources.map((source) => (
                    <li key={`${source.title}-${source.publisher}`}>
                      {source.url ? (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          dir="ltr"
                        >
                          {source.title}
                        </a>
                      ) : (
                        <span>{source.title}</span>
                      )}{" "}
                      <span className="card__meta">
                        — {source.publisher} ·{" "}
                        {txToken(tx, locale, "ev.src", source.source_status)}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            <p className="card__meta">
              <time className="num" dateTime={result.created_at}>
                {new Date(result.created_at).toLocaleString()}
              </time>{" "}
              · <span className="num" dir="ltr" lang="en">{result.provider_or_model}</span>
            </p>
          </details>
        </>
      ) : (
        <p className="empty-note">🌾 {t("agent.empty")}</p>
      )}
    </section>
  );
}

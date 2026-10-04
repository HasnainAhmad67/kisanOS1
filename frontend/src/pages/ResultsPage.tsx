import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, getResults } from "../api/client";
import { AgentCard } from "../components/AgentCard";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { useAssessment } from "../hooks/useAssessment";
import { translate, useI18n, type DictKey } from "../i18n";
import type {
  AgentId,
  AgentResult,
  AssessmentResults,
  AssessmentResultsResponse,
} from "../types/backend";

const AGENT_ORDER: AgentId[] = ["weather", "water", "crop", "vision", "market"];

function isPending(
  data: AssessmentResultsResponse,
): data is Extract<AssessmentResultsResponse, { events: unknown }> {
  return "events" in data && data.farm_plan === null && !("created_at" in data);
}

/**
 * Results — GET /assessments/{id}/results. Five agent cards in fixed
 * order, then the farm plan (safety banner, ≤3 prioritized checks,
 * conflicts, verification step). No fabricated content: missing agents
 * render an honest "not returned" note. Cards stagger in on load.
 */
export function ResultsPage() {
  const navigate = useNavigate();
  const { assessment, reset } = useAssessment();
  const { t, locale } = useI18n();

  const [data, setData] = useState<AssessmentResultsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!assessment) return;
    setLoading(true);
    setError(null);
    try {
      const results = await getResults(
        assessment.assessmentId,
        assessment.accessToken,
      );
      setData(results);
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : t("results.errorEmpty"),
      );
    } finally {
      setLoading(false);
    }
  }, [assessment, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function startNewCheck() {
    reset();
    navigate("/");
  }

  function PageHeading() {
    return (
      <h1 className="page-title">
        {t("results.title")}
        {locale === "ur" ? (
          <span className="label-en" dir="ltr">
            {translate("en", "results.title")}
          </span>
        ) : null}
      </h1>
    );
  }

  if (loading) {
    return (
      <div className="page page--results stack">
        <img
          className="page-tex"
          src="/images/farm-aerial.jpg"
          alt=""
          loading="lazy"
          decoding="async"
          aria-hidden="true"
        />
        <PageHeading />
        <p className="loading-line">
          <span className="spinner" aria-hidden="true" />
          {t("results.loading")}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page page--results stack">
        <img
          className="page-tex"
          src="/images/farm-aerial.jpg"
          alt=""
          loading="lazy"
          decoding="async"
          aria-hidden="true"
        />
        <PageHeading />
        <Alert>{error}</Alert>
        <p className="empty-note">🌾 {t("results.errorEmpty")}</p>
        <Button block onClick={() => void load()}>
          {t("common.tryAgain")}
        </Button>
        <Button block variant="secondary" onClick={startNewCheck}>
          {t("results.startNew")}
        </Button>
      </div>
    );
  }

  if (data && isPending(data)) {
    const failed = data.status === "failed";
    return (
      <div className="page page--results stack">
        <img
          className="page-tex"
          src="/images/farm-aerial.jpg"
          alt=""
          loading="lazy"
          decoding="async"
          aria-hidden="true"
        />
        <PageHeading />
        {failed ? <Alert>{t("results.failed")}</Alert> : (
          <p className="page-intro">⏳ {t("results.pending")}</p>
        )}
        <LinkButton to="/analysis" block>
          {failed ? t("results.retryAnalysis") : t("results.backAnalysis")}
        </LinkButton>
        <Button block variant="secondary" onClick={startNewCheck}>
          {t("results.startNew")}
        </Button>
      </div>
    );
  }

  const full = data as AssessmentResults | null;
  const agentById = new Map<AgentId, AgentResult>(
    (full?.agents ?? []).map((agent) => [agent.agent_id, agent]),
  );
  const plan = full?.farm_plan ?? null;
  const explanation = full?.ai_explanation ?? null;

  // Reason for a skipped/failed explanation — i18n with raw-key fallback.
  const explanationReason = explanation?.reason
    ? txReason(explanation.reason)
    : null;

  function txReason(reason: string): string {
    return translate(locale, ("exp." + reason) as DictKey) || reason;
  }

  return (
    <div className="page page--results stack">
      <img
        className="page-tex"
        src="/images/farm-aerial.jpg"
        alt=""
        loading="lazy"
        decoding="async"
        aria-hidden="true"
      />
      <PageHeading />
      <p className="page-intro">{t("results.intro")}</p>

      {full && full.status === "failed" ? (
        <Alert>{t("results.jobFailed")}</Alert>
      ) : null}

      <div className="agent-grid">
        {AGENT_ORDER.map((agentId) => (
          <AgentCard
            key={agentId}
            agentId={agentId}
            result={agentById.get(agentId) ?? null}
          />
        ))}
      </div>

      {plan ? (
        <Card tone="safety" title={t("plan.title")}>
          {/* Safety banner: Urdu primary in Urdu mode; the backend's
              authoritative English wording always remains visible. */}
          <p className="plan-banner">
            {locale === "ur" ? t("safety.banner") : plan.safety_banner}
          </p>
          {locale === "ur" ? (
            <p className="label-en" dir="ltr" style={{ marginTop: 0 }}>
              {plan.safety_banner}
            </p>
          ) : null}

          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="card__meta">{t("plan.fieldStatus")}</span>
            <StatusBadge status={plan.status} prominent />
          </div>
          <p style={{ marginBlockStart: "var(--space-3)" }}>{plan.rationale}</p>

          {plan.checks.length > 0 ? (
            <>
              <h3 style={{ marginBlockStart: "var(--space-4)" }}>
                {t("plan.checks")}
              </h3>
              <ol className="plan-checks">
                {plan.checks.slice(0, 3).map((check, index) => (
                  <li key={check.id} style={{ "--step": index + 1 } as CSSProperties}>
                    <strong className="plan-checks__title">{check.title}</strong>
                    <p style={{ margin: 0 }}>{check.how_to_check}</p>
                    <p className="empty-note" style={{ margin: 0 }}>
                      {t("plan.why")} {check.why}
                    </p>
                    <p className="empty-note" style={{ margin: 0 }}>
                      {t("plan.watch")} {check.what_to_observe}
                    </p>
                    {check.evidence_labels.length > 0 ? (
                      <p className="card__meta">
                        {check.evidence_labels.join(" · ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>
            </>
          ) : null}

          {plan.conflicts.length > 0 ? (
            <>
              <h3 style={{ marginBlockStart: "var(--space-4)" }}>
                {t("plan.conflicts")}
              </h3>
              <ul className="agent-card__list">
                {plan.conflicts.map((conflict, index) => (
                  <li key={index}>
                    {conflict.topic ? `${conflict.topic}: ` : ""}
                    {Array.isArray(conflict.findings)
                      ? conflict.findings.join("; ")
                      : null}
                    {conflict.next_check
                      ? ` ${t("plan.nextCheck")} ${conflict.next_check}`
                      : ""}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          <h3 style={{ marginBlockStart: "var(--space-4)" }}>
            {t("plan.verification")}
          </h3>
          <p>{plan.verification_step}</p>
          <p className="card__meta">
            {t("plan.policy")} <span className="num">{plan.policy_version}</span>
          </p>
        </Card>
      ) : (
        <Card tone="safety" title={t("plan.title")}>
          <p className="empty-note" style={{ margin: 0 }}>
            🌾 {t("plan.empty")}
          </p>
        </Card>
      )}

      <Card tone="info" title={t("exp.title")}>
        {explanation &&
        explanation.status === "complete" &&
        explanation.farmer_summary ? (
          <>
            <p style={{ margin: 0 }}>{explanation.farmer_summary}</p>
            <p className="card__meta">{explanation.disclaimer}</p>
          </>
        ) : (
          <p className="empty-note" style={{ margin: 0 }}>
            {t("exp.unavailable")}
            {explanationReason ? ` — ${explanationReason}` : ""}.{" "}
            {t("exp.authoritative")}
          </p>
        )}
      </Card>

      <div className="stack">
        <LinkButton to="/followup" variant="secondary" block>
          {t("results.followup")}
        </LinkButton>
        <Button block variant="secondary" onClick={startNewCheck}>
          {t("results.startNew")}
        </Button>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, getResults } from "../api/client";
import { AgentCard } from "../components/AgentCard";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { useAssessment } from "../hooks/useAssessment";
import type {
  AgentId,
  AgentResult,
  AssessmentResults,
  AssessmentResultsResponse,
} from "../types/backend";

const AGENT_ORDER: AgentId[] = ["weather", "water", "crop", "vision", "market"];

const EXPLANATION_REASONS: Record<string, string> = {
  consent_missing: "explanation consent was not given",
  disabled: "the explanation service is switched off",
  key_missing: "no explanation key is configured",
  timeout: "the explanation service timed out",
  provider_error: "the explanation provider had an error",
  invalid_output: "the explanation returned unusable output",
};

function isPending(
  data: AssessmentResultsResponse,
): data is Extract<AssessmentResultsResponse, { events: unknown }> {
  return "events" in data && data.farm_plan === null && !("created_at" in data);
}

/**
 * Results — GET /assessments/{id}/results. Five agent cards in fixed
 * order, then the farm plan (safety banner, ≤3 prioritized checks,
 * conflicts, verification step). No fabricated content: missing agents
 * render an honest "not returned" note.
 */
export function ResultsPage() {
  const navigate = useNavigate();
  const { assessment, reset } = useAssessment();

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
        cause instanceof ApiError ? cause.message : "Results are unavailable.",
      );
    } finally {
      setLoading(false);
    }
  }, [assessment]);

  useEffect(() => {
    void load();
  }, [load]);

  function startNewCheck() {
    reset();
    navigate("/");
  }

  if (loading) {
    return (
      <div className="stack">
        <h1>
          Nateejay
          <span className="label-en">Your results</span>
        </h1>
        <p className="loading-line">
          <span className="spinner" aria-hidden="true" />
          Nateejay aa rahe hain… Loading results
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="stack">
        <h1>
          Nateejay
          <span className="label-en">Your results</span>
        </h1>
        <Alert>{error}</Alert>
        <p className="empty-note">
          🌾 Results nahi milay — check your connection and try once more.
        </p>
        <Button block onClick={() => void load()}>
          Try again
        </Button>
        <Button block variant="secondary" onClick={startNewCheck}>
          Naya Check — Start New Check
        </Button>
      </div>
    );
  }

  if (data && isPending(data)) {
    const failed = data.status === "failed";
    return (
      <div className="stack">
        <h1>
          Nateejay
          <span className="label-en">Your results</span>
        </h1>
        {failed ? (
          <Alert>
            Analysis mukammal nahi ho saka (the analysis did not finish).
            Retry it from the analysis screen.
          </Alert>
        ) : (
          <p className="page-intro">
            ⏳ Analysis abhi chal raha hai — Nateejay yahan dikhenge jab job
            mukammal ho jaye (results appear once the job finishes).
          </p>
        )}
        <LinkButton to="/analysis" block>
          {failed ? "Retry analysis" : "Back to analysis"}
        </LinkButton>
        <Button block variant="secondary" onClick={startNewCheck}>
          Naya Check — Start New Check
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

  return (
    <div className="stack">
      <h1>
        Nateejay
        <span className="label-en">Your results</span>
      </h1>
      <p className="page-intro">
        Screening support only — a plan below is not a confirmed diagnosis.
      </p>

      {full && full.status === "failed" ? (
        <Alert>
          The analysis job reported a failure. Some cards may be incomplete.
        </Alert>
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
        <Card tone="safety" title="Farm Plan — Aapka Khet Plan">
          <p className="plan-banner">{plan.safety_banner}</p>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="card__meta">Field status</span>
            <StatusBadge status={plan.status} prominent />
          </div>
          <p style={{ marginBlockStart: "var(--space-3)" }}>{plan.rationale}</p>

          {plan.checks.length > 0 ? (
            <>
              <h3 style={{ marginBlockStart: "var(--space-4)" }}>
                Prioritized checks
              </h3>
              <ol className="plan-checks">
                {plan.checks.slice(0, 3).map((check) => (
                  <li key={check.id}>
                    <strong>
                      {check.priority}. {check.title}
                    </strong>
                    <p style={{ margin: 0 }}>{check.how_to_check}</p>
                    <p className="empty-note" style={{ margin: 0 }}>
                      Why: {check.why}
                    </p>
                    <p className="empty-note" style={{ margin: 0 }}>
                      Watch for: {check.what_to_observe}
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
                Conflicting evidence
              </h3>
              <ul className="agent-card__list">
                {plan.conflicts.map((conflict, index) => (
                  <li key={index}>
                    {conflict.topic ? `${conflict.topic}: ` : ""}
                    {Array.isArray(conflict.findings)
                      ? conflict.findings.join("; ")
                      : null}
                    {conflict.next_check ? ` Next check: ${conflict.next_check}` : ""}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          <h3 style={{ marginBlockStart: "var(--space-4)" }}>
            Verification step
          </h3>
          <p>{plan.verification_step}</p>
          <p className="card__meta">Policy {plan.policy_version}</p>
        </Card>
      ) : (
        <Card tone="safety" title="Farm Plan — Aapka Khet Plan">
          <p className="empty-note" style={{ margin: 0 }}>
            🌾 Koi plan nahi bana — no farm plan was produced for this check
            (the analysis may have failed or been interrupted). Retry the
            analysis to build a plan.
          </p>
        </Card>
      )}

      <Card tone="info" title="Explanation">
        {explanation && explanation.status === "complete" && explanation.farmer_summary ? (
          <>
            <p style={{ margin: 0 }}>{explanation.farmer_summary}</p>
            <p className="card__meta">{explanation.disclaimer}</p>
          </>
        ) : (
          <p className="empty-note" style={{ margin: 0 }}>
            Explanation unavailable
            {explanation?.reason
              ? ` — ${EXPLANATION_REASONS[explanation.reason] ?? explanation.reason}`
              : ""}
            . The farm plan above stays authoritative.
          </p>
        )}
      </Card>

      <div className="stack">
        <LinkButton to="/followup" variant="secondary" block>
          Record a follow-up
        </LinkButton>
        <Button block variant="secondary" onClick={startNewCheck}>
          Naya Check — Start New Check
        </Button>
      </div>
    </div>
  );
}

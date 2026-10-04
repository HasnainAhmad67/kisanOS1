import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, getJob, startAnalysis } from "../api/client";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { useAssessment } from "../hooks/useAssessment";
import { translate, useI18n } from "../i18n";
import type { JobState, JobStatus } from "../types/backend";

const TERMINAL: JobState[] = ["succeeded", "partial", "failed"];

function humanize(phase: string): string {
  return phase.replace(/_/g, " ");
}

/**
 * Analysis progress — POST /assessments/{id}/analyze then GET /jobs/{id}
 * polled every second. Only real backend events are rendered; the step
 * tracker derives checkmarks from those events (no fake percentages).
 * Terminal success routes to results, failure offers retry.
 */
export function AnalysisProgressPage() {
  const navigate = useNavigate();
  const { assessment, setJobId } = useAssessment();
  const { t, locale, tx } = useI18n();

  const [job, setJob] = useState<JobStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPolling() {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function handleStart() {
    if (!assessment) return;
    setError(null);
    setStarting(true);
    stopPolling();
    try {
      const accepted = await startAnalysis(
        assessment.assessmentId,
        assessment.accessToken,
      );
      if ("agents" in accepted) {
        // Serverless mode: the full AssessmentResults came back inline
        // (HTTP 200) — no polling; jump straight to the results page.
        setJobId(accepted.job_id);
        setStarting(false);
        navigate("/results");
        return;
      }
      setJobId(accepted.job_id);
      setJob({
        job_id: accepted.job_id,
        assessment_id: assessment.assessmentId,
        state: accepted.state,
        events: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        error_code: null,
      });
      pollOnce(accepted.job_id);
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : t("analysis.failed"),
      );
      setStarting(false);
    }
  }

  async function pollOnce(jobId: string) {
    if (!assessment) return;
    try {
      const status = await getJob(jobId, assessment.accessToken);
      applyJob(status);
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : t("analysis.failed"),
      );
    }
  }

  function applyJob(status: JobStatus) {
    setJob(status);
    setStarting(false);
    if (TERMINAL.includes(status.state)) {
      stopPolling();
      if (status.state === "succeeded" || status.state === "partial") {
        navigate("/results");
      }
      // failed → retry button rendered below
    }
  }

  // Poll every 1s while a non-terminal job is known.
  useEffect(() => {
    if (!assessment || !job) return;
    if (TERMINAL.includes(job.state)) return;
    if (pollRef.current !== null) return;
    pollRef.current = setInterval(() => {
      void pollOnce(job.job_id);
    }, 1000);
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.job_id, job?.state, assessment]);

  // Refresh restore: if a job id came from sessionStorage, resume polling.
  useEffect(() => {
    if (assessment?.jobId && !job) {
      void pollOnce(assessment.jobId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assessment?.jobId]);

  /** Phase tracker derived strictly from real backend events. */
  const tracker = useMemo(() => {
    if (!job || job.events.length === 0) return [];
    const order: string[] = [];
    const lastStatus = new Map<string, string>();
    for (const event of job.events) {
      if (!order.includes(event.phase)) order.push(event.phase);
      lastStatus.set(event.phase, event.status);
    }
    return order.map((phase) => {
      const status = lastStatus.get(phase) ?? "started";
      return {
        phase,
        status,
        done: status !== "started",
      };
    });
  }, [job]);

  const currentPhase = tracker.find((item) => !item.done);
  const failed = job?.state === "failed";
  const badgeStatus =
    job?.state === "succeeded"
      ? "complete"
      : job?.state === "failed"
        ? "error"
        : job?.state === "partial"
          ? "partial"
          : "pending";

  return (
    <div className="page page--analysis stack">
      <img
        className="page-tex"
        src="/images/hero-wheat-field.jpg"
        alt=""
        loading="lazy"
        decoding="async"
        aria-hidden="true"
      />
      <h1 className="page-title">
        {t("analysis.title")}
        {locale === "ur" ? (
          <span className="label-en" dir="ltr">
            {translate("en", "analysis.title")}
          </span>
        ) : null}
      </h1>
      <p className="page-intro">{t("analysis.intro")}</p>

      {error ? <Alert>{error}</Alert> : null}

      <Card
        title={t("analysis.progressTitle")}
        meta={job ? tx(`status.${job.state}`, job.state) : undefined}
      >
        {job && !TERMINAL.includes(job.state) ? (
          <p className="loading-line">
            <span className="spinner" aria-hidden="true" />
            {currentPhase
              ? `${tx(`phase.${currentPhase.phase}`, humanize(currentPhase.phase))}…`
              : t("analysis.live")}
          </p>
        ) : null}

        {tracker.length > 0 ? (
          <div className="tracker">
            <p className="card__meta">{t("analysis.trackerTitle")}</p>
            <ol className="phase-track">
              {tracker.map((item) => (
                <li
                  key={item.phase}
                  className={`phase-track__item${item.done ? " is-done" : " is-current"}`}
                  aria-current={item.done ? undefined : "step"}
                >
                  <span className="phase-track__mark" aria-hidden="true">
                    {item.done ? "✓" : "•"}
                  </span>
                  <span>
                    {tx(`phase.${item.phase}`, humanize(item.phase))}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        {job ? (
          <>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="card__meta">{t("analysis.jobStatus")}</span>
              <StatusBadge status={badgeStatus} pulse={!TERMINAL.includes(job.state)} />
            </div>
            {job.events.length > 0 ? (
              <details className="event-details" open>
                <summary>{t("analysis.rawEvents")}</summary>
                <ol className="event-list">
                  {job.events.map((event) => (
                    <li key={`${event.sequence}-${event.phase}`}>
                      <span className="event-list__phase">
                        {tx(`phase.${event.phase}`, humanize(event.phase))}
                      </span>{" "}
                      <span
                        className={`event-list__status event-list__status--${event.status}`}
                      >
                        {tx(`evstatus.${event.status}`, event.status)}
                      </span>
                      {event.detail ? (
                        <span className="event-list__detail"> — {event.detail}</span>
                      ) : null}{" "}
                      <time
                        className="num"
                        dateTime={event.timestamp}
                      >
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </time>
                    </li>
                  ))}
                </ol>
              </details>
            ) : (
              <p className="empty-note">{t("analysis.waitingFirst")}</p>
            )}
          </>
        ) : (
          <p className="empty-note">{t("analysis.notStarted")}</p>
        )}
        {failed ? (
          <Alert>
            {t("analysis.failed")}
            {job?.error_code ? ` (${job.error_code})` : ""}
          </Alert>
        ) : null}
      </Card>

      <div className="stack">
        {!failed ? (
          <Button block onClick={handleStart} disabled={starting || !!job}>
            {starting
              ? t("analysis.starting")
              : job
                ? t("analysis.running")
                : t("analysis.start")}
          </Button>
        ) : (
          <Button block onClick={handleStart} disabled={starting}>
            {starting ? t("analysis.retrying") : t("analysis.retry")}
          </Button>
        )}
        <LinkButton to="/photos" variant="secondary" block>
          {t("analysis.backPhotos")}
        </LinkButton>
      </div>
    </div>
  );
}

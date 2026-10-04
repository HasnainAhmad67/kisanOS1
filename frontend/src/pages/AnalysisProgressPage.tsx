import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, getJob, startAnalysis } from "../api/client";
import { Alert } from "../components/Alert";
import { Button, LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { useAssessment } from "../hooks/useAssessment";
import type { JobState, JobStatus } from "../types/backend";

const TERMINAL: JobState[] = ["succeeded", "partial", "failed"];

/**
 * Analysis progress — POST /assessments/{id}/analyze then GET /jobs/{id}
 * polled every second. Only real backend events are rendered; no fake
 * percentages. Terminal success routes to results, failure offers retry.
 */
export function AnalysisProgressPage() {
  const navigate = useNavigate();
  const { assessment, setJobId } = useAssessment();

  const [job, setJob] = useState<JobStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Track polling in a ref so a stale interval never keeps running.
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
        cause instanceof ApiError
          ? cause.message
          : "Could not start the analysis. Try again.",
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
        cause instanceof ApiError
          ? cause.message
          : "Lost contact while checking progress.",
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
    if (pollRef.current !== null) return; // already polling
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

  const failed = job?.state === "failed";

  return (
    <div className="stack">
      <h1>Analysis</h1>
      <p className="page-intro">
        Five agents check weather, water, crop, photos, and market evidence —
        usually within a minute.
      </p>

      {error ? <Alert>{error}</Alert> : null}

      <Card
        title="Progress"
        meta={job ? job.state : undefined}
      >
        {job ? (
          <>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="card__meta">Job status</span>
              <StatusBadge
                status={
                  job.state === "succeeded"
                    ? "complete"
                    : job.state === "failed"
                      ? "error"
                      : job.state === "partial"
                        ? "partial"
                        : "pending"
                }
              />
            </div>
            {job.events.length > 0 ? (
              <ol className="event-list">
                {job.events.map((event) => (
                  <li key={`${event.sequence}-${event.phase}`}>
                    <span className="event-list__phase">{event.phase}</span>{" "}
                    <span
                      className={`event-list__status event-list__status--${event.status}`}
                    >
                      {event.status.replace(/_/g, " ")}
                    </span>
                    {event.detail ? (
                      <span className="event-list__detail">
                        {" "}
                        — {event.detail}
                      </span>
                    ) : null}
                    <span className="card__meta">
                      {" "}
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty-note">
                Waiting for the first backend event…
              </p>
            )}
          </>
        ) : (
          <p className="empty-note">
            The analysis has not started yet. Press Start Analysis — progress
            below comes straight from the backend job.
          </p>
        )}
        {failed ? (
          <Alert>
            Analysis failed
            {job?.error_code ? ` (${job.error_code})` : ""}. You can retry.
          </Alert>
        ) : null}
      </Card>

      <div className="stack">
        {!failed ? (
          <Button block onClick={handleStart} disabled={starting || !!job}>
            {starting
              ? "Starting…"
              : job
                ? "Analysis running…"
                : "Start Analysis"}
          </Button>
        ) : (
          <Button block onClick={handleStart} disabled={starting}>
            {starting ? "Retrying…" : "Retry Analysis"}
          </Button>
        )}
        <LinkButton to="/photos" variant="secondary" block>
          Back to photos
        </LinkButton>
      </div>
    </div>
  );
}

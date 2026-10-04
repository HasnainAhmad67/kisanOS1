/**
 * KisanOS API client.
 *
 * Same-origin in development: the Vite dev server proxies /api to
 * http://localhost:8000 (see vite.config.ts), so no CORS handling lives here.
 * Authenticated calls send the assessment access token as X-Assessment-Token.
 *
 * Every function mirrors an existing backend route; shapes come from
 * src/types/backend.ts (mirrors of backend/app/schemas.py).
 */

import type {
  AnalyzeResponse,
  ApiErrorBody,
  AssessmentCreatePayload,
  AssessmentCreated,
  AssessmentDeleted,
  AssessmentResultsResponse,
  FollowUpCreated,
  FollowUpCreatePayload,
  ImageUploadResponse,
  JobStatus,
  PublicConfig,
  ViewType,
} from "../types/backend";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  token?: string | null;
  json?: unknown;
  form?: FormData;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.token) {
    headers["X-Assessment-Token"] = options.token;
  }

  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form; // browser sets the multipart boundary itself
  } else if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
    });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "Cannot reach the KisanOS API. Check your connection and try again.",
    );
  }

  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed with HTTP ${response.status}`;
    let requestId: string | null = response.headers.get("X-Request-ID");
    try {
      const detail: unknown = await response.json();
      const err = (typeof detail === "object" && detail !== null
        ? ((detail as { detail?: unknown }).detail ?? detail)
        : null) as Partial<ApiErrorBody> | string | null;
      if (typeof err === "string") {
        message = err;
      } else if (err) {
        code = err.code ?? code;
        message = err.message ?? message;
        requestId = err.request_id ?? requestId;
      }
    } catch {
      /* keep the defaults above */
    }
    throw new ApiError(response.status, code, message, requestId);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/* ------------------------------------------------------------- routes --- */

/** POST /api/v1/assessments */
export function createAssessment(
  payload: AssessmentCreatePayload,
): Promise<AssessmentCreated> {
  return request<AssessmentCreated>("/assessments", {
    method: "POST",
    json: payload,
  });
}

/** POST /api/v1/assessments/{id}/images (multipart: file + view_type) */
export function uploadImage(
  assessmentId: string,
  token: string,
  file: File,
  viewType: ViewType,
): Promise<ImageUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("view_type", viewType);
  return request<ImageUploadResponse>(
    `/assessments/${encodeURIComponent(assessmentId)}/images`,
    { method: "POST", token, form },
  );
}

/** POST /api/v1/assessments/{id}/analyze — 202 queued job (local) or 200 inline results (serverless). */
export function startAnalysis(
  assessmentId: string,
  token: string,
): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(
    `/assessments/${encodeURIComponent(assessmentId)}/analyze`,
    { method: "POST", token },
  );
}

/** GET /api/v1/jobs/{job_id} (token also accepted via X-Assessment-Token) */
export function getJob(jobId: string, token: string): Promise<JobStatus> {
  return request<JobStatus>(`/jobs/${encodeURIComponent(jobId)}`, { token });
}

/** GET /api/v1/assessments/{id}/results */
export function getResults(
  assessmentId: string,
  token: string,
): Promise<AssessmentResultsResponse> {
  return request<AssessmentResultsResponse>(
    `/assessments/${encodeURIComponent(assessmentId)}/results`,
    { token },
  );
}

/** POST /api/v1/assessments/{id}/followups */
export function addFollowup(
  assessmentId: string,
  token: string,
  payload: FollowUpCreatePayload,
): Promise<FollowUpCreated> {
  return request<FollowUpCreated>(
    `/assessments/${encodeURIComponent(assessmentId)}/followups`,
    { method: "POST", token, json: payload },
  );
}

/** DELETE /api/v1/assessments/{id} (cascades results, follow-ups, images) */
export function deleteAssessment(
  assessmentId: string,
  token: string,
): Promise<AssessmentDeleted> {
  return request<AssessmentDeleted>(
    `/assessments/${encodeURIComponent(assessmentId)}`,
    { method: "DELETE", token },
  );
}

/** GET /api/v1/config — public runtime configuration (no auth). */
export function getConfig(): Promise<PublicConfig> {
  return request<PublicConfig>("/config");
}

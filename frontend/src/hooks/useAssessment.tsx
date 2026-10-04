import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import type {
  AssessmentCreatePayload,
  AssessmentCreated,
  ViewType,
} from "../types/backend";

/**
 * Shared assessment session.
 * Only assessmentId + accessToken + jobId are persisted — and only in
 * sessionStorage (cleared when the tab closes). The access token is never
 * put in a URL.
 */

const STORAGE_KEY = "kisanos.assessment";

export interface StoredAssessment {
  assessmentId: string;
  accessToken: string;
  jobId?: string;
}

function readStored(): StoredAssessment | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredAssessment>;
    if (parsed.assessmentId && parsed.accessToken) {
      return {
        assessmentId: parsed.assessmentId,
        accessToken: parsed.accessToken,
        jobId: parsed.jobId,
      };
    }
  } catch {
    /* corrupt storage → start fresh */
  }
  return null;
}

function persist(value: StoredAssessment | null): void {
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable (private mode) — state still lives in memory */
  }
}

interface UploadedItem {
  name: string;
  viewType: ViewType;
  imageId: string;
  qualityPassed: boolean;
}

interface AssessmentContextValue {
  assessment: StoredAssessment | null;
  intake: AssessmentCreatePayload | null;
  uploads: UploadedItem[];
  /** POST /assessments succeeded → store ids (persisted) + intake (memory). */
  startAssessment: (created: AssessmentCreated, intake: AssessmentCreatePayload) => void;
  /** Persist the analysis job id (survives refresh so polling can resume). */
  setJobId: (jobId: string) => void;
  /** Record a successful upload (memory only). */
  recordUpload: (item: UploadedItem) => void;
  /** "Start New Check" — clears state + sessionStorage. */
  reset: () => void;
}

const AssessmentContext = createContext<AssessmentContextValue | null>(null);

export function AssessmentProvider({ children }: { children: ReactNode }) {
  const [assessment, setAssessment] = useState<StoredAssessment | null>(readStored);
  const [intake, setIntake] = useState<AssessmentCreatePayload | null>(null);
  const [uploads, setUploads] = useState<UploadedItem[]>([]);

  const startAssessment = useCallback(
    (created: AssessmentCreated, payload: AssessmentCreatePayload) => {
      const next: StoredAssessment = {
        assessmentId: created.assessment_id,
        accessToken: created.access_token,
      };
      persist(next);
      setAssessment(next);
      setIntake(payload);
      setUploads([]);
    },
    [],
  );

  const setJobId = useCallback((jobId: string) => {
    setAssessment((current) => {
      const next: StoredAssessment = {
        assessmentId: current?.assessmentId ?? "",
        accessToken: current?.accessToken ?? "",
        jobId,
      };
      if (!next.assessmentId || !next.accessToken) return current;
      persist(next);
      return next;
    });
  }, []);

  const recordUpload = useCallback((item: UploadedItem) => {
    setUploads((current) => [...current, item]);
  }, []);

  const reset = useCallback(() => {
    persist(null);
    setAssessment(null);
    setIntake(null);
    setUploads([]);
  }, []);

  const value: AssessmentContextValue = {
    assessment,
    intake,
    uploads,
    startAssessment,
    setJobId,
    recordUpload,
    reset,
  };

  return (
    <AssessmentContext.Provider value={value}>
      {children}
    </AssessmentContext.Provider>
  );
}

export function useAssessment(): AssessmentContextValue {
  const value = useContext(AssessmentContext);
  if (!value) {
    throw new Error("useAssessment must be used inside <AssessmentProvider>");
  }
  return value;
}

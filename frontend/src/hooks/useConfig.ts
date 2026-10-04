import { useEffect, useState } from "react";
import { getConfig } from "../api/client";
import type { PublicConfig } from "../types/backend";

interface UseConfigResult {
  config: PublicConfig | null;
  error: string | null;
  loading: boolean;
}

/** Loads GET /api/v1/config once (public, unauthenticated). */
export function useConfig(): UseConfigResult {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((value) => {
        if (!cancelled) {
          setConfig(value);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof Error ? cause.message : "Configuration unavailable",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { config, error, loading };
}

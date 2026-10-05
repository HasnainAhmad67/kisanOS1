import { useI18n } from "../i18n";
import { matchBackendText } from "../i18n/backendText";

interface BackendTextProps {
  /** Raw English string coming from the backend. */
  text: string;
  className?: string;
}

/**
 * Renders one backend string in the UI language.
 *
 * - English UI → the backend's English, unchanged.
 * - Urdu UI + a known, fixed sentence → the Urdu wording from
 *   `i18n/backendText.ts` (never machine-translated on the fly).
 * - Urdu UI + `"<known label>: <detail>"` → Urdu label with the dynamic
 *   detail kept as readable LTR English.
 * - Urdu UI + anything else → the English original under the visible label
 *   "اصل نظامی پیغام (English)", so nothing safety-critical is hidden.
 */
export function BackendText({ text, className }: BackendTextProps) {
  const { locale, t } = useI18n();
  const classes = className ? `backend-en ${className}` : "backend-en";

  if (!text.trim()) return null;

  if (locale !== "ur") {
    return (
      <span className={classes} lang="en">
        {text}
      </span>
    );
  }

  const match = matchBackendText(text);

  if (!match) {
    return (
      <span className={classes}>
        <span className="backend-en__label">{t("results.originalText")}</span>
        <span className="backend-en__text" dir="ltr" lang="en">
          {text}
        </span>
      </span>
    );
  }

  if (match.rest === null) {
    return (
      <span className={classes} lang="ur">
        {match.urdu}
      </span>
    );
  }

  // Known Urdu label + short dynamic English tail (e.g. a model detail).
  return (
    <span className={classes}>
      <span lang="ur">{match.urdu}</span>{" "}
      <span className="backend-en__inline" dir="ltr" lang="en">
        {match.rest}
      </span>
    </span>
  );
}

import { useI18n, type DictKey } from "../i18n";
import type { AgentStatus, PlanStatus } from "../types/backend";

type BadgeStatus = AgentStatus | PlanStatus | "pending";

const STYLES: Record<BadgeStatus, string> = {
  /* AgentResult.status */
  complete: "badge--complete",
  partial: "badge--partial",
  stale: "badge--info",
  unavailable: "badge--neutral",
  not_assessed: "badge--neutral",
  unsupported: "badge--neutral",
  error: "badge--safety",
  /* FarmPlan.status — green / amber / red */
  insufficient_information: "badge--neutral",
  monitor: "badge--complete", // green
  field_inspection_recommended: "badge--partial", // amber
  expert_review_recommended: "badge--safety", // red
  /* shell placeholder — not a backend status */
  pending: "badge--neutral",
};

export function StatusBadge({
  status,
  prominent = false,
  pulse = false,
}: {
  status: BadgeStatus;
  /** Larger, presentation-weight badge (Farm Plan status). */
  prominent?: boolean;
  /** Subtle pulse for live/running states. */
  pulse?: boolean;
}) {
  const { t } = useI18n();
  const classes = [
    "badge",
    STYLES[status],
    prominent ? "badge--lg" : "",
    pulse ? "badge--pulse" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const label = t(("status." + status) as DictKey);
  return <span className={classes}>{label}</span>;
}

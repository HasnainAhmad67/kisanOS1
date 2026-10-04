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
  /* FarmPlan.status */
  insufficient_information: "badge--neutral",
  monitor: "badge--info",
  field_inspection_recommended: "badge--partial",
  expert_review_recommended: "badge--safety",
  /* shell placeholder — not a backend status */
  pending: "badge--neutral",
};

function label(status: BadgeStatus): string {
  if (status === "pending") return "pending";
  return status.replace(/_/g, " ");
}

export function StatusBadge({ status }: { status: BadgeStatus }) {
  return <span className={`badge ${STYLES[status]}`}>{label(status)}</span>;
}

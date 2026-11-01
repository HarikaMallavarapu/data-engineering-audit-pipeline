import type { RunStatus } from "../../services/runService";

interface StatusBadgeProps {
  status: RunStatus | string;
  size?: "default" | "small";
}

export function StatusBadge({ status, size = "default" }: StatusBadgeProps) {
  const label = status.toLowerCase().replaceAll("_", " ");
  return <span className={`status-badge status-${label.replaceAll(" ", "-")}${size === "small" ? " status-small" : ""}`}>
    <span className="status-dot" aria-hidden="true" />{label}
  </span>;
}

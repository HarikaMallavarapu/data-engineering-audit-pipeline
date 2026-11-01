import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  note: string;
  icon: ReactNode;
  tone?: "teal" | "blue" | "amber" | "violet" | "neutral";
}

export function MetricCard({ label, value, note, icon, tone = "neutral" }: MetricCardProps) {
  return (
    <div className={`metric-card metric-${tone}`} role="group" aria-label={`${label}: ${value}`}>
      <div className="metric-topline"><span>{label}</span><span className="metric-icon" aria-hidden="true">{icon}</span></div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-note">{note}</span>
    </div>
  );
}

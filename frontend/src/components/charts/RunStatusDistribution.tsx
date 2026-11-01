import type { PipelineRun } from "../../services/runService";
import { formatNumber } from "../../utils/format";

interface RunStatusDistributionProps {
  runs: PipelineRun[];
}

const statuses = [
  { value: "SUCCESS", label: "Succeeded", color: "success" },
  { value: "PARTIAL", label: "Partial", color: "partial" },
  { value: "FAILED", label: "Failed", color: "failed" },
  { value: "RUNNING", label: "Running", color: "running" },
  { value: "PENDING", label: "Pending", color: "pending" },
  { value: "CANCELLED", label: "Cancelled", color: "cancelled" },
] as const;

const radius = 45;
const circumference = 2 * Math.PI * radius;

export function RunStatusDistribution({ runs }: RunStatusDistributionProps) {
  const counts = statuses.map((status) => ({
    ...status,
    count: runs.filter((run) => run.status === status.value).length,
  }));
  const total = counts.reduce((sum, status) => sum + status.count, 0);
  if (total === 0) return <div className="outcome-empty"><strong>0</strong><span>No run outcomes in this time range.</span></div>;

  let offset = 0;
  return <div className="status-distribution">
    <figure className="status-ring" aria-hidden="true">
      <svg viewBox="0 0 120 120" focusable="false">
        <circle cx="60" cy="60" r={radius} className="status-ring-track" />
        {counts.filter((status) => status.count > 0).map((status) => {
          const portion = status.count / total * circumference;
          const circle = <circle key={status.value} cx="60" cy="60" r={radius} className={`status-ring-segment status-ring-${status.color}`} strokeDasharray={`${portion} ${circumference - portion}`} strokeDashoffset={-offset} />;
          offset += portion;
          return circle;
        })}
      </svg>
      <span className="status-ring-center"><strong>{formatNumber(total)}</strong><small>runs</small></span>
    </figure>
    <ul className="status-legend" aria-label="Run counts by status">
      {counts.map((status) => <li key={status.value}><span className={`status-legend-dot status-legend-${status.color}`} aria-hidden="true" /><span>{status.label}</span><strong>{formatNumber(status.count)}</strong></li>)}
    </ul>
  </div>;
}

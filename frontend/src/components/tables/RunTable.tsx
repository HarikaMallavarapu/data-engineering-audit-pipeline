import { Link } from "react-router-dom";

import { StatusBadge } from "../common/StatusBadge";
import type { PipelineRun } from "../../services/runService";
import { formatDate, formatNumber, shortId } from "../../utils/format";

interface RunTableProps {
  runs: PipelineRun[];
  caption: string;
  emptyMessage?: string;
}

export function RunTable({ runs, caption, emptyMessage = "No pipeline runs have been recorded yet." }: RunTableProps) {
  if (runs.length === 0) return <p className="table-empty">{emptyMessage}</p>;
  return (
    <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="data-table">
        <caption className="visually-hidden">{caption}</caption>
        <thead><tr><th scope="col">Run</th><th scope="col">Status</th><th scope="col">Input</th><th scope="col">Accepted</th><th scope="col">Rejected</th><th scope="col">Created</th><th scope="col"><span className="visually-hidden">Open</span></th></tr></thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id}>
              <td><Link className="table-primary-link" to={`/runs/${encodeURIComponent(run.run_id)}`}>{shortId(run.run_id)}</Link><span className="table-secondary">{run.pipeline_id}</span></td>
              <td><StatusBadge status={run.status} size="small" /></td>
              <td className="numeric-cell">{formatNumber(run.counts.input)}</td>
              <td className="numeric-cell">{formatNumber(run.counts.accepted)}</td>
              <td className="numeric-cell">{formatNumber(run.counts.rejected)}</td>
              <td>{formatDate(run.created_at)}</td>
              <td><Link className="table-action" to={`/runs/${encodeURIComponent(run.run_id)}`}>View</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

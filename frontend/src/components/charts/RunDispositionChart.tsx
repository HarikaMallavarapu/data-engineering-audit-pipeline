import { useId } from "react";
import { formatNumber } from "../../utils/format";

export interface RunDispositionPoint {
  label: string;
  axisLabel: string;
  runId: string;
  accepted: number;
  rejected: number;
  duplicates: number;
}

interface RunDispositionChartProps {
  data: RunDispositionPoint[];
}

const series = [
  { key: "accepted", label: "Accepted", gradient: "accepted" },
  { key: "rejected", label: "Rejected", gradient: "rejected" },
  { key: "duplicates", label: "Duplicates", gradient: "duplicate" },
] as const;

const chart = { width: 760, height: 284, left: 48, right: 14, top: 18, bottom: 42 };

function areaPath(upper: number[], lower: number[], x: number[], y: (value: number) => number): string {
  const upperPath = upper.map((value, index) => `${index === 0 ? "M" : "L"}${x[index]?.toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const lowerPath = lower.map((value, index) => `L${x[index]?.toFixed(1)},${y(value).toFixed(1)}`).reverse().join(" ");
  return `${upperPath} ${lowerPath} Z`;
}

function visibleTickIndexes(length: number): number[] {
  if (length <= 3) return Array.from({ length }, (_, index) => index);
  const count = 5;
  return [...new Set(Array.from({ length: count }, (_, index) => Math.round((length - 1) * index / (count - 1))))];
}

export function RunDispositionChart({ data }: RunDispositionChartProps) {
  const id = useId().replaceAll(":", "");
  const plotWidth = chart.width - chart.left - chart.right;
  const plotHeight = chart.height - chart.top - chart.bottom;
  const totals = data.map((point) => point.accepted + point.rejected + point.duplicates);
  const maxValue = Math.max(1, ...totals);
  const tickValues = [...new Set([0, Math.round(maxValue / 2), maxValue])];
  const y = (value: number) => chart.top + plotHeight - value / maxValue * plotHeight;
  const x = data.map((_, index) => data.length === 1
    ? chart.left + plotWidth / 2
    : chart.left + plotWidth * index / (data.length - 1));
  const tickIndexes = visibleTickIndexes(data.length);

  return <figure className="run-chart-figure" aria-label="Run row dispositions by execution">
    <svg className="run-disposition-chart" viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-labelledby={`run-chart-title-${id} run-chart-description-${id}`}>
      <title id={`run-chart-title-${id}`}>Accepted, rejected, and duplicate rows by run</title>
      <desc id={`run-chart-description-${id}`}>Stacked area chart of persisted row counts, ordered by execution time. Open the chart data table for exact timestamps, run IDs, and counts without using hover.</desc>
      <defs>
        <linearGradient id={`accepted-fill-${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--chart-accepted)" stopOpacity=".42" /><stop offset="100%" stopColor="var(--chart-accepted)" stopOpacity=".04" /></linearGradient>
        <linearGradient id={`rejected-fill-${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--chart-rejected)" stopOpacity=".46" /><stop offset="100%" stopColor="var(--chart-rejected)" stopOpacity=".08" /></linearGradient>
        <linearGradient id={`duplicate-fill-${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--chart-duplicate)" stopOpacity=".55" /><stop offset="100%" stopColor="var(--chart-duplicate)" stopOpacity=".1" /></linearGradient>
      </defs>
      {tickValues.map((tick) => <g key={tick}>
        <line x1={chart.left} x2={chart.width - chart.right} y1={y(tick)} y2={y(tick)} className="chart-grid-line" />
        <text x={chart.left - 10} y={y(tick) + 3.5} textAnchor="end" className="chart-axis-label">{tick.toLocaleString()}</text>
      </g>)}
      {data.length > 1 ? (() => {
        let lower = data.map(() => 0);
        return series.map(({ key, gradient }) => {
          const upper = data.map((point, index) => (lower[index] ?? 0) + point[key]);
          const path = areaPath(upper, lower, x, y);
          lower = upper;
          return <path key={key} d={path} className={`disposition-area disposition-area-${key}`} fill={`url(#${gradient}-fill-${id})`} />;
        });
      })() : null}
      {data.length === 1 && data.map((point, index) => {
        const width = 30;
        let currentY = y(0);
        return <g key={point.runId}>
          {series.map(({ key, label, gradient }) => {
            const height = point[key] / maxValue * plotHeight;
            currentY -= height;
            return <rect key={key} x={(x[index] ?? chart.left) - width / 2} y={currentY} width={width} height={height} rx="2" fill={`url(#${gradient}-fill-${id})`} stroke={`var(--chart-${gradient === "duplicate" ? "duplicate" : gradient})`}><title>{`${point.label} · ${point.runId} · ${label}: ${point[key].toLocaleString()}`}</title></rect>;
          })}
        </g>;
      })}
      {data.length > 1 && data.map((point, index) => <circle key={point.runId} cx={x[index]} cy={y(totals[index] ?? 0)} r="3.5" className="chart-point">
        <title>{`${point.label} · ${point.runId} · accepted ${point.accepted.toLocaleString()} · rejected ${point.rejected.toLocaleString()} · duplicates ${point.duplicates.toLocaleString()}`}</title>
      </circle>)}
      {tickIndexes.map((index) => <text key={data[index]?.runId ?? index} x={x[index]} y={chart.height - 14} textAnchor="middle" className="chart-axis-label"><title>{data[index]?.label}</title>{data[index]?.axisLabel}</text>)}
    </svg>
    <figcaption className="chart-legend">{series.map(({ key, label }) => <span key={key}><i className={`legend-swatch legend-${key}`} aria-hidden="true" />{label}</span>)}</figcaption>
    <details className="chart-data-details">
      <summary>View chart data</summary>
      <div className="table-scroll" role="region" aria-label="Run volume chart values" tabIndex={0}>
        <table className="data-table chart-data-table">
          <caption className="visually-hidden">Exact values plotted in the run volume chart</caption>
          <thead><tr><th scope="col">Run ID</th><th scope="col">Created</th><th scope="col">Accepted</th><th scope="col">Rejected</th><th scope="col">Duplicates</th></tr></thead>
          <tbody>{data.map((point) => <tr key={point.runId}><td><code>{point.runId}</code></td><td>{point.label}</td><td className="numeric-cell">{formatNumber(point.accepted)}</td><td className="numeric-cell">{formatNumber(point.rejected)}</td><td className="numeric-cell">{formatNumber(point.duplicates)}</td></tr>)}</tbody>
        </table>
      </div>
    </details>
    <ul className="visually-hidden">{data.map((point) => <li key={point.runId}>{point.label}, run {point.runId}: accepted {point.accepted}, rejected {point.rejected}, duplicates {point.duplicates}</li>)}</ul>
  </figure>;
}

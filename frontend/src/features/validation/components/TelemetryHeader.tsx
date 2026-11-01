import { Activity, Database, Gauge, ShieldCheck, TestTube2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getValidationAnalytics, getValidationCatalog, listQualityBaselines } from "../../../services/runService";
import { formatNumber } from "../../../utils/format";

export function TelemetryHeader({ demoPreviewCount = 0 }: { demoPreviewCount?: number }) {
  const catalog = useQuery({
    queryKey: ["validation-catalog", "telemetry"],
    queryFn: () => getValidationCatalog({ page: 1, pageSize: 1 }),
    refetchInterval: 30_000,
  });
  const analytics = useQuery({
    queryKey: ["validation-analytics", "telemetry"],
    queryFn: () => getValidationAnalytics({ days: 30 }),
    refetchInterval: 30_000,
  });
  const baselines = useQuery({
    queryKey: ["quality-baselines", "telemetry"],
    queryFn: () => listQualityBaselines({ page: 1, pageSize: 1 }),
    refetchInterval: 30_000,
  });
  const sourceMissing = catalog.data?.source_status === "SOURCE_MISSING" || catalog.data?.source_status === "NOT_IMPORTED";
  const catalogValue = catalog.data ? formatNumber(catalog.data.total) : "—";
  const catalogNote = sourceMissing
    ? `${formatNumber(demoPreviewCount)} synthetic preview rows · 0 imported`
    : catalog.data?.source_status === "PARTIAL"
      ? "Partial source import"
      : "Imported definitions";
  const latency = analytics.data?.average_execution_time_ms;

  return <section className="validation-telemetry" aria-label="Validation system telemetry">
    <div className="validation-telemetry-item"><Database size={15} aria-hidden="true" /><span><small>Registered checks</small><strong>{catalog.isError ? "Unavailable" : catalogValue}</strong><em>{catalogNote}</em></span></div>
    <div className="validation-telemetry-item"><ShieldCheck size={15} aria-hidden="true" /><span><small>Fully implemented</small><strong>{catalog.data ? formatNumber(catalog.data.counts.FULLY_IMPLEMENTED ?? 0) : "—"}</strong><em>{sourceMissing ? "No source definitions" : "Database status count"}</em></span></div>
    <div className="validation-telemetry-item"><Activity size={15} aria-hidden="true" /><span><small>Baseline drift index</small><strong>—</strong><em>{baselines.data?.total ? `${formatNumber(baselines.data.total)} baselines · index not persisted` : "No measured index"}</em></span></div>
    <div className="validation-telemetry-item"><TestTube2 size={15} aria-hidden="true" /><span><small>Pipeline test coverage</small><strong>—</strong><em>Coverage report not configured</em></span></div>
    <div className="validation-telemetry-item"><Gauge size={15} aria-hidden="true" /><span><small>Execution latency / SLA</small><strong>{latency === null || latency === undefined ? "—" : `${Math.round(latency)} ms`}</strong><em>{analytics.data ? "Observed check runtime · no SLA configured" : "No persisted samples"}</em></span></div>
  </section>;
}

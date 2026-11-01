import { Route, Routes } from "react-router-dom";

import { MainLayout } from "../components/layout/MainLayout";
import { AuditPage } from "../features/audit/AuditPage";
import { CopilotPage } from "../features/copilot/CopilotPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { IncidentsPage } from "../features/incidents/IncidentsPage";
import { LineagePage } from "../features/lineage/LineagePage";
import { PipelinesPage } from "../features/pipelines/PipelinesPage";
import { QualityPage } from "../features/data-quality/QualityPage";
import { QuarantinePage } from "../features/quarantine/QuarantinePage";
import { ReconciliationPage } from "../features/reconciliation/ReconciliationPage";
import { DuplicatesPage } from "../features/quarantine/DuplicatesPage";
import { EnginePage } from "../features/engine/EnginePage";
import { RunDetailsPage } from "../features/runs/RunDetailsPage";
import { RunsPage } from "../features/runs/RunsPage";
import { SourcesPage } from "../features/sources/SourcesPage";
import { NotFoundPage } from "../features/NotFoundPage";
import { RunValidationResultsPage } from "../features/validation/RunValidationResultsPage";
import { ValidationCatalogPage } from "../features/validation/ValidationCatalogPage";
import { ValidationHistoryPage } from "../features/validation/ValidationHistoryPage";
import { ValidationOverviewPage } from "../features/validation/ValidationOverviewPage";
import { ValidationBaselinesPage } from "../features/validation/ValidationBaselinesPage";
import { RuleStudioPage } from "../features/validation/RuleStudioPage";
import { ValidationCenter } from "../pages/ValidationCenter";

export function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="pipelines" element={<PipelinesPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="runs/:runId" element={<RunDetailsPage />} />
        <Route path="engine" element={<EnginePage />} />
        <Route path="quality" element={<QualityPage />} />
        <Route path="validation" element={<ValidationCenter />} />
        <Route path="validation/overview" element={<ValidationOverviewPage />} />
        <Route path="validation/catalog" element={<ValidationCatalogPage />} />
        <Route path="validation/history" element={<ValidationHistoryPage />} />
        <Route path="validation/baselines" element={<ValidationBaselinesPage />} />
        <Route path="validation/rules" element={<RuleStudioPage />} />
        <Route path="validation/results" element={<RunValidationResultsPage />} />
        <Route path="quarantine" element={<QuarantinePage />} />
        <Route path="duplicates" element={<DuplicatesPage />} />
        <Route path="reconciliation" element={<ReconciliationPage />} />
        <Route path="lineage" element={<LineagePage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="copilot" element={<CopilotPage />} />
        <Route path="audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

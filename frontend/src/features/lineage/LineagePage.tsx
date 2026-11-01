import { GitBranch } from "lucide-react";
import { Link } from "react-router-dom";

import { StatePanel } from "../../components/common/StatePanel";

export function LineagePage() {
  return <div className="page-content">
    <div className="unavailable-heading"><span className="section-icon section-icon-blue" aria-hidden="true"><GitBranch size={18} /></span><div><p className="eyebrow">PROVENANCE WORKSPACE</p><h1>Lineage explorer</h1><p className="page-description">Trace a published record back to its source and processing stages.</p></div></div>
    <StatePanel tone="info" title="Lineage API is not available yet" message="The current backend stores source IDs, source row numbers, run and artifact references, but does not expose a lineage endpoint for interactive traversal. No lineage graph is inferred in the browser." action={<Link className="button button-secondary" to="/runs">Review run evidence</Link>} />
  </div>;
}

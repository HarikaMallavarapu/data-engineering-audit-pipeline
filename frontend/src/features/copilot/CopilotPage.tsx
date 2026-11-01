import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { StatePanel } from "../../components/common/StatePanel";

export function CopilotPage() {
  return <div className="page-content">
    <div className="unavailable-heading"><span className="section-icon section-icon-violet" aria-hidden="true"><Sparkles size={18} /></span><div><p className="eyebrow">EVIDENCE-GROUNDED ASSISTANCE</p><h1>AI Copilot</h1><p className="page-description">Investigate real run evidence with clearly labeled diagnostic suggestions.</p></div></div>
    <StatePanel tone="info" title="Copilot diagnosis is not connected" message="The backend copilot route is a scaffold and currently returns no diagnosis contract. No prompt is submitted and no generated explanation is shown." action={<Link className="button button-secondary" to="/runs">Open run evidence</Link>} />
  </div>;
}

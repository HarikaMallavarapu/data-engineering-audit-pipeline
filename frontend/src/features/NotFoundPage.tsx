import { Link } from "react-router-dom";

export function NotFoundPage() {
  return <main className="not-found-page"><p className="eyebrow">404 · WORKSPACE ROUTE</p><h1>This page is not available</h1><p>The route does not match a DataTrace workspace page.</p><Link className="button button-primary" to="/">Return to command center</Link></main>;
}

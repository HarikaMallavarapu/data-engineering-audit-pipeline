import { Menu, Moon, Sun, X } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useTheme } from "../../app/ThemeProvider";

interface HeaderProps {
  apiState: "checking" | "online" | "offline";
  mobileNavigationOpen: boolean;
  onMobileNavigationToggle: () => void;
}

function getPageLabel(pathname: string): string {
  if (pathname.startsWith("/runs/")) return "Run evidence";
  const route = pathname.split("/").filter(Boolean)[0] ?? "";
  const labels: Record<string, string> = {
    "": "Command center",
    sources: "Sources",
    pipelines: "Pipelines",
    runs: "Pipeline runs",
    engine: "Data engine",
    quality: "Data quality",
    quarantine: "Quarantine",
    duplicates: "Duplicates",
    reconciliation: "Reconciliation",
    lineage: "Lineage",
    incidents: "Failure outcomes",
    copilot: "AI Copilot",
    audit: "Audit log",
  };
  return labels[route] ?? "Workspace";
}

export function Header({ apiState, mobileNavigationOpen, onMobileNavigationToggle }: HeaderProps) {
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const labels = { checking: "Checking API", online: "API connected", offline: "API unavailable" };
  const nextTheme = theme === "light" ? "dark" : "light";
  const ThemeIcon = theme === "light" ? Moon : Sun;
  const MobileMenuIcon = mobileNavigationOpen ? X : Menu;

  return (
    <header className="topbar">
      <button
        className="icon-button mobile-menu-toggle"
        type="button"
        onClick={onMobileNavigationToggle}
        aria-label={mobileNavigationOpen ? "Close navigation menu" : "Open navigation menu"}
        aria-expanded={mobileNavigationOpen}
        aria-controls="mobile-navigation"
      >
        <MobileMenuIcon size={18} aria-hidden="true" />
      </button>
      <div className="breadcrumb"><Link to="/">DataTrace</Link><span aria-hidden="true">/</span><strong>{getPageLabel(location.pathname)}</strong></div>
      <div className="header-actions">
        <div className={`api-indicator api-${apiState}`} role="status" aria-live="polite">
          <span className="api-dot" aria-hidden="true" />{labels[apiState]}
        </div>
        <span className="header-divider" aria-hidden="true" />
        <button className="icon-button theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${nextTheme} theme`} aria-pressed={theme === "dark"}>
          <ThemeIcon size={17} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}

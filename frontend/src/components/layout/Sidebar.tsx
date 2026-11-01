import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  BadgeCheck,
  BarChart3,
  BookOpenCheck,
  ClipboardList,
  Database,
  FileSearch,
  GitBranch,
  History,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  SlidersHorizontal,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NavLink } from "react-router-dom";

interface NavigationItem {
  to: string;
  label: string;
  Icon: LucideIcon;
  end?: boolean;
  available: boolean;
}

interface NavigationSection {
  label: string;
  items: NavigationItem[];
}

export const navigationSections: NavigationSection[] = [
  { label: "Overview", items: [{ to: "/", label: "Command center", Icon: LayoutDashboard, end: true, available: true }] },
  { label: "Data operations", items: [
    { to: "/sources", label: "Sources", Icon: Database, available: true },
    { to: "/pipelines", label: "Pipelines", Icon: Workflow, available: true },
    { to: "/runs", label: "Pipeline runs", Icon: Activity, available: true },
    { to: "/engine", label: "Data engine", Icon: SlidersHorizontal, available: true },
  ] },
  { label: "Validation Center", items: [
    { to: "/validation", label: "Overview", Icon: BadgeCheck, end: true, available: true },
    { to: "/validation/catalog", label: "Validation catalog", Icon: BookOpenCheck, available: true },
    { to: "/validation/results", label: "Run validation results", Icon: ShieldCheck, available: true },
    { to: "/validation/history", label: "Validation history", Icon: History, available: true },
    { to: "/validation/rules", label: "Rule Studio", Icon: SlidersHorizontal, available: true },
    { to: "/validation/baselines", label: "Baselines and drift", Icon: BarChart3, available: true },
  ] },
  { label: "Data quality", items: [
    { to: "/quality", label: "Data quality", Icon: ShieldCheck, available: true },
    { to: "/quarantine", label: "Quarantine", Icon: FileSearch, available: true },
    { to: "/duplicates", label: "Duplicates", Icon: FileSearch, available: true },
    { to: "/reconciliation", label: "Reconciliation", Icon: ArrowLeftRight, available: true },
  ] },
  { label: "Traceability", items: [
    { to: "/lineage", label: "Lineage", Icon: GitBranch, available: false },
    { to: "/audit", label: "Audit log", Icon: ClipboardList, available: true },
  ] },
  { label: "Operations", items: [
    { to: "/incidents", label: "Failure outcomes", Icon: AlertTriangle, available: true },
    { to: "/copilot", label: "AI Copilot", Icon: Sparkles, available: false },
  ] },
];

function NavigationLinks({ onNavigate, collapsed = false }: { onNavigate?: () => void; collapsed?: boolean }) {
  return <nav className="primary-navigation" aria-label="Primary navigation">
    {navigationSections.map((section) => (
      <div className="nav-section" key={section.label}>
        <p className="nav-section-title">{section.label}</p>
        <div className="nav-items">
          {section.items.map(({ to, label, Icon, end, available }) => (
            <NavLink
              key={to}
              className={({ isActive }) => `nav-link${isActive ? " nav-link-active" : ""}${available ? "" : " nav-link-limited"}`}
              to={to}
              end={end}
              onClick={onNavigate}
              aria-label={collapsed ? (available ? label : `${label} (not yet available)`) : undefined}
              title={collapsed ? (available ? label : `${label} · not yet available`) : undefined}
            >
              <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
              <span>{label}</span>
              {!available ? <span className="nav-soon">Later</span> : null}
            </NavLink>
          ))}
        </div>
      </div>
    ))}
  </nav>;
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const SidebarToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;
  return (
    <aside className={`sidebar${collapsed ? " sidebar-collapsed" : ""}`} aria-label="DataTrace workspace">
      <div className="sidebar-brand-row">
        <NavLink className="brand" to="/" aria-label={collapsed ? "DataTrace" : undefined}>
          <span className="brand-mark" aria-hidden="true"><Activity size={18} strokeWidth={2.2} /></span>
          <span className="brand-copy"><strong>DataTrace</strong><small>DATA OPERATIONS</small></span>
        </NavLink>
        <button className="icon-button sidebar-collapse-toggle" type="button" onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          <SidebarToggleIcon size={16} aria-hidden="true" />
        </button>
      </div>
      <NavigationLinks collapsed={collapsed} />
      <div className="sidebar-footer">
        <span className="environment-indicator" aria-hidden="true" />
        <span><strong>Local workspace</strong><small>Single-node development</small></span>
      </div>
    </aside>
  );
}

export function MobileNavigation({ isOpen, onNavigate }: { isOpen: boolean; onNavigate: () => void }) {
  return <div id="mobile-navigation" className="mobile-navigation" hidden={!isOpen}>
    <NavigationLinks onNavigate={onNavigate} />
  </div>;
}

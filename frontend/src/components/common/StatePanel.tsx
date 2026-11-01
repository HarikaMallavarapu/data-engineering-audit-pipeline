import { AlertTriangle, Inbox, LoaderCircle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type StateTone = "loading" | "error" | "empty" | "info";

const icons: Record<StateTone, LucideIcon> = {
  loading: LoaderCircle,
  error: AlertTriangle,
  empty: Inbox,
  info: Inbox,
};

interface StatePanelProps {
  tone: StateTone;
  title: string;
  message: string;
  action?: ReactNode;
  compact?: boolean;
}

export function StatePanel({ tone, title, message, action, compact = false }: StatePanelProps) {
  const Icon = icons[tone];
  return (
    <div className={`state-panel state-${tone}${compact ? " state-compact" : ""}`} role={tone === "error" ? "alert" : tone === "loading" ? "status" : undefined}>
      <span className="state-icon" aria-hidden="true"><Icon size={18} strokeWidth={1.8} /></span>
      <div className="state-copy">
        <strong>{title}</strong>
        <p>{message}</p>
        {action ? <div className="state-action">{action}</div> : null}
      </div>
    </div>
  );
}

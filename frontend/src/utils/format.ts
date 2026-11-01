export function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

export function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return "In progress";
  const elapsed = Math.max(0, new Date(completedAt).getTime() - new Date(startedAt).getTime());
  return elapsed < 1000 ? `${elapsed} ms` : `${(elapsed / 1000).toFixed(2)} s`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function shortId(value: string, length = 18): string {
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

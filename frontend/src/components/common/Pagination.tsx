import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <nav className="pagination" aria-label="Table pagination">
      <span className="pagination-summary">{start}–{end} of {total}</span>
      <div className="pagination-actions">
        <button type="button" className="icon-button" aria-label="Previous page" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft size={16} aria-hidden="true" />
        </button>
        <span className="pagination-page">Page {page} of {pageCount}</span>
        <button type="button" className="icon-button" aria-label="Next page" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}

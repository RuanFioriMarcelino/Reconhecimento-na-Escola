export default function PaginationBar({ pagination, onPageChange, onPageSizeChange }) {
  if (!pagination) return null;
  const { page, pageSize, total, totalPages, hasNext, hasPrev } = pagination;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-2.5 text-xs text-ink-soft shadow-sm">
      <div>
        Mostrando <strong>{start}–{end}</strong> de <strong>{total}</strong> · Página <strong>{page}</strong> de <strong>{totalPages}</strong>
      </div>
      <div className="flex items-center gap-2">
        {onPageSizeChange && (
          <select
            aria-label="Itens por página"
            value={pageSize}
            onChange={e => onPageSizeChange(Number(e.target.value))}
            style={{ width: 'auto', padding: '4px 8px', fontSize: 12 }}
          >
            {[15, 24, 25, 50, 100].map(sz => (
              <option key={sz} value={sz}>{sz}/pág</option>
            ))}
          </select>
        )}
        <button
          type="button"
          className="btn btn-ghost"
          style={{ padding: '5px 11px', fontSize: 12 }}
          disabled={!hasPrev}
          onClick={() => onPageChange(page - 1)}
        >
          Anterior
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ padding: '5px 11px', fontSize: 12 }}
          disabled={!hasNext}
          onClick={() => onPageChange(page + 1)}
        >
          Próxima
        </button>
      </div>
    </div>
  );
}

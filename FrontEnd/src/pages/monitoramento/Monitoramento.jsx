import { useCallback, useEffect, useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import PaginationBar from '../../components/PaginationBar.jsx';
import { cx } from '../../lib/cx.js';
import { api } from '../../lib/api.js';
import MonitoramentoRow from './MonitoramentoRow.jsx';

const FIELD_BASE =
  'rounded-[7px] border border-line bg-surface font-body text-[13.5px] ' +
  'leading-[normal] text-ink focus:border-primary focus:outline-none';

const SEARCH_INPUT = cx(FIELD_BASE, 'w-full pl-[34px] pr-3 py-[9px]');
const SELECT = cx(FIELD_BASE, 'w-full max-w-[175px] px-3 py-[9px]');

export default function Monitoramento({ dispositivos = [], liveTick = 0, onNavigate }) {
  const [busca, setBusca] = useState('');
  const [debouncedBusca, setDebouncedBusca] = useState('');
  const [tipoPessoa, setTipoPessoa] = useState('');
  const [tipoEvento, setTipoEvento] = useState('');
  const [status, setStatus] = useState('');
  const [de, setDe] = useState('');
  const [ate, setAte] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, pageSize: 25, total: 0, totalPages: 1, hasNext: false, hasPrev: false });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedBusca(busca);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [busca]);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listLogs({
        search: debouncedBusca,
        tipo_pessoa: tipoPessoa,
        tipo_evento: tipoEvento,
        status,
        de,
        ate,
        page,
        page_size: pageSize,
      });
      setItems(res.items || []);
      if (res.pagination) setPagination(res.pagination);
      setLoadError('');
    } catch (err) {
      setLoadError(err?.message || 'Não foi possível carregar os registros de monitoramento.');
    } finally {
      setLoading(false);
    }
  }, [debouncedBusca, tipoPessoa, tipoEvento, status, de, ate, page, pageSize]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Atualiza automaticamente apenas se o operador estiver observando a página 1 (mais recentes)
  useEffect(() => {
    if (liveTick > 0 && page === 1) {
      fetchLogs();
    }
  }, [liveTick, page, fetchLogs]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display m-0 mb-1 text-[23px] font-semibold">Monitoramento em tempo real</h1>
          <p className="m-0 text-sm text-ink-soft">
            <span className="mr-1.5 inline-block h-[7px] w-[7px] rounded-full bg-good animate-pulse-dot" />
            Consulta paginada no PostgreSQL · {pagination.total} registro(s) encontrado(s)
          </p>
        </div>
      </div>

      {dispositivos.length > 0 && (
        <div className="mb-5 flex flex-wrap gap-2.5">
          {dispositivos.map(d => (
            <div key={d.id} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-sm">
              <span className={cx('inline-block size-2 rounded-full', d.online ? 'bg-good' : 'bg-ink-faint')} />
              <strong>{d.portal}</strong>
              <span className="text-ink-faint">· {d.online ? `Online (${d.telemetria?.fps || '—'} FPS)` : 'Offline'}</span>
            </div>
          ))}
        </div>
      )}

      <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[210px] flex-1">
          <Icon
            name="search"
            size={16}
            className="pointer-events-none absolute left-[11px] top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <input
            className={SEARCH_INPUT}
            placeholder="Buscar por nome ou portal"
            value={busca}
            onChange={e => setBusca(e.target.value)}
          />
        </div>
        <select className={SELECT} value={tipoPessoa} onChange={e => { setTipoPessoa(e.target.value); setPage(1); }}>
          <option value="">Alunos e funcionários</option>
          <option value="aluno">Somente alunos</option>
          <option value="funcionario">Somente funcionários</option>
        </select>
        <select className={SELECT} value={tipoEvento} onChange={e => { setTipoEvento(e.target.value); setPage(1); }}>
          <option value="">Entradas e saídas</option>
          <option value="entrada">Somente entradas</option>
          <option value="saida">Somente saídas</option>
        </select>
        <select className={SELECT} value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Todos os status</option>
          <option value="reconhecido">Reconhecido</option>
          <option value="atraso">Atraso</option>
          <option value="saida-antecipada">Saída antecipada</option>
          <option value="nao-reconhecido">Não reconhecido</option>
        </select>
        <input type="date" value={de} onChange={e => { setDe(e.target.value); setPage(1); }} style={{ width: 145 }} title="Data inicial" />
        <input type="date" value={ate} onChange={e => { setAte(e.target.value); setPage(1); }} style={{ width: 145 }} title="Data final" />
      </div>

      {loadError && (
        <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-danger bg-danger-soft px-4 py-2.5 text-sm text-ink">
          <span>{loadError}</span>
          <button type="button" className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={fetchLogs}>
            Tentar novamente
          </button>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-line bg-surface shadow">
        {loading && items.length === 0 ? (
          <div className="p-10 text-center text-ink-faint">Consultando registros...</div>
        ) : items.length ? (
          <table className="w-full border-collapse text-[13.5px]">
            <thead>
              <tr>
                {['Data / Hora', 'Pessoa', 'Tipo', 'Turma/Cargo', 'Movimento', 'Portal', 'Confiança', 'Status'].map(h => (
                  <th
                    key={h}
                    className="border-b border-line px-3 pb-2.5 pt-3 text-left text-[11.5px] font-semibold text-ink-faint"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map(l => (
                <MonitoramentoRow key={l.id} log={l} onNavigate={onNavigate} />
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-10 text-center text-ink-faint">Nenhum registro para esse filtro.</div>
        )}
      </div>

      <PaginationBar
        pagination={pagination}
        onPageChange={setPage}
        onPageSizeChange={sz => {
          setPageSize(sz);
          setPage(1);
        }}
      />
    </div>
  );
}

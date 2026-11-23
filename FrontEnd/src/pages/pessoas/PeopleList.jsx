import { useCallback, useEffect, useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import Avatar from '../../components/Avatar.jsx';
import Button from '../../components/ui/Button.jsx';
import PaginationBar from '../../components/PaginationBar.jsx';
import { BiometriaPill } from '../../components/Pills.jsx';
import { cx } from '../../lib/cx.js';
import { api } from '../../lib/api.js';
import { PERSON_CONFIG } from '../../data/seed.js';

const FIELD_BASE =
  'rounded-[7px] border border-line bg-surface font-body text-[13.5px] ' +
  'leading-[normal] text-ink focus:border-primary focus:outline-none';

const SEARCH_INPUT = cx(FIELD_BASE, 'w-full pl-[34px] pr-3 py-[9px]');
const SELECT = cx(FIELD_BASE, 'w-full max-w-[190px] px-3 py-[9px]');

export default function PeopleList({ tipo, turmas = [], liveTick = 0, onNavigate }) {
  const cfg = PERSON_CONFIG[tipo];
  const [busca, setBusca] = useState('');
  const [debouncedBusca, setDebouncedBusca] = useState('');
  const [grupo, setGrupo] = useState('');
  const [biometria, setBiometria] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(24);
  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, pageSize: 24, total: 0, totalPages: 1, hasNext: false, hasPrev: false });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const grupoOptions =
    tipo === 'aluno' && turmas.length > 0 ? turmas.map(t => t.nome) : cfg.grupoOptions;

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedBusca(busca);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [busca]);

  useEffect(() => {
    setPage(1);
    setBusca('');
    setDebouncedBusca('');
    setGrupo('');
    setBiometria('');
  }, [tipo]);

  const fetchPeople = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listPeople({
        tipo,
        search: debouncedBusca,
        grupo,
        biometria,
        page,
        page_size: pageSize,
      });
      setItems(res.items || []);
      if (res.pagination) setPagination(res.pagination);
      setLoadError('');
    } catch (err) {
      setLoadError(err?.message || 'Não foi possível carregar a listagem.');
    } finally {
      setLoading(false);
    }
  }, [tipo, debouncedBusca, grupo, biometria, page, pageSize]);

  useEffect(() => {
    fetchPeople();
  }, [fetchPeople, liveTick]);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display m-0 mb-1 text-[23px] font-semibold">{cfg.plural}</h1>
          <p className="m-0 text-sm text-ink-soft">
            {pagination.total} {cfg.plural.toLowerCase()} encontrado(s) no PostgreSQL
          </p>
        </div>
        <Button variant="primary" onClick={() => onNavigate('cadastro', tipo)}>
          <Icon name="userplus" size={16} /> Novo cadastro
        </Button>
      </div>

      <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[230px] flex-1">
          <Icon
            name="search"
            size={16}
            className="pointer-events-none absolute left-[11px] top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <input
            className={SEARCH_INPUT}
            placeholder={'Buscar por nome ou ' + cfg.documentoLabel.toLowerCase()}
            value={busca}
            onChange={e => setBusca(e.target.value)}
          />
        </div>
        <select
          className={SELECT}
          value={grupo}
          onChange={e => {
            setGrupo(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{'Todos: ' + cfg.grupoLabel.toLowerCase()}</option>
          {grupoOptions.map(g => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
        <select
          className={SELECT}
          value={biometria}
          onChange={e => {
            setBiometria(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Toda biometria</option>
          <option value="sim">Biometria ativa</option>
          <option value="nao">Biometria pendente</option>
        </select>
      </div>

      {loadError && (
        <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-danger bg-danger-soft px-4 py-2.5 text-sm text-ink">
          <span>{loadError}</span>
          <button type="button" className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={fetchPeople}>
            Tentar novamente
          </button>
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="rounded-lg border border-line bg-surface p-10 text-center text-ink-faint shadow">
          Carregando registros...
        </div>
      ) : items.length ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3">
          {items.map(p => (
            <button
              key={p.id}
              className="flex cursor-pointer items-start gap-3 rounded-lg border border-line bg-surface p-3.5 text-left shadow transition-colors hover:border-primary"
              onClick={() => onNavigate('pessoa', tipo, p.id)}
            >
              <Avatar nome={p.nome} size={44} />
              <div className="min-w-0 flex-1">
                <strong className="mb-0.5 block truncate text-[13.5px] font-semibold">{p.nome}</strong>
                <div className="mb-2 text-xs text-ink-faint">
                  {p.grupo} · {cfg.documentoLabel} {p.documento}
                </div>
                {p.status === 'inativo' ? (
                  <span className="pill pill-neutral">Inativo</span>
                ) : (
                  <BiometriaPill cadastrada={p.biometriaCadastrada} qualidade={p.biometriaQualidade} />
                )}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2.5 rounded-lg border border-line bg-surface px-5 py-10 text-center text-ink-faint shadow">
          <Icon name={cfg.icon} size={30} className="opacity-60" />
          <div>Nenhum registro encontrado para esse filtro.</div>
        </div>
      )}

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

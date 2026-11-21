import { useCallback, useEffect, useState } from 'react';
import PaginationBar from '../../components/PaginationBar.jsx';
import { api } from '../../lib/api.js';
import AlertCard from './AlertCard.jsx';

export default function Alertas({ liveTick = 0, onAlertChanged, showToast }) {
  const [status, setStatus] = useState('');
  const [severidade, setSeveridade] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [items, setItems] = useState([]);
  const [openCount, setOpenCount] = useState(0);
  const [pagination, setPagination] = useState({ page: 1, pageSize: 20, total: 0, totalPages: 1, hasNext: false, hasPrev: false });
  const [loading, setLoading] = useState(true);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listAlerts({ status, severidade, page, page_size: pageSize });
      setItems(res.items || []);
      setOpenCount(res.openCount ?? 0);
      if (res.pagination) setPagination(res.pagination);
    } finally {
      setLoading(false);
    }
  }, [status, severidade, page, pageSize]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  useEffect(() => {
    if (liveTick > 0 && page === 1) {
      fetchAlerts();
    }
  }, [liveTick, page, fetchAlerts]);

  async function handleUpdateStatus(alertId, nextStatus) {
    try {
      await api.updateAlert(alertId, { status: nextStatus });
      showToast(nextStatus === 'resolvido' ? 'Alerta marcado como resolvido' : 'Alerta atualizado para em análise', 'check');
      await fetchAlerts();
      if (onAlertChanged) onAlertChanged();
    } catch (error) {
      showToast(error.message || 'Erro ao atualizar alerta.', 'triangle');
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Alertas e avisos da portaria</h1>
          <p>{openCount} alerta(s) aguardando atenção da coordenação</p>
        </div>
      </div>

      <div className="filters">
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Todos os status</option>
          <option value="abertos">Apenas em aberto</option>
          <option value="novo">Novo</option>
          <option value="em-analise">Em análise</option>
          <option value="resolvido">Resolvido</option>
        </select>
        <select value={severidade} onChange={e => { setSeveridade(e.target.value); setPage(1); }}>
          <option value="">Todas as severidades</option>
          <option value="alta">Alta</option>
          <option value="media">Média</option>
          <option value="baixa">Baixa</option>
        </select>
      </div>

      {loading && items.length === 0 ? (
        <div className="card empty">Carregando alertas...</div>
      ) : items.length ? (
        items.map(a => <AlertCard key={a.id} alert={a} onUpdateStatus={handleUpdateStatus} />)
      ) : (
        <div className="card empty">Nenhum alerta para esse filtro.</div>
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

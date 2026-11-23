import { useCallback, useEffect, useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import RingChart from '../../components/RingChart.jsx';
import { api } from '../../lib/api.js';

export default function Relatorios({ liveTick = 0, showToast }) {
  const [de, setDe] = useState('');
  const [ate, setAte] = useState('');
  const [exporting, setExporting] = useState(false);
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState('');

  const loadReports = useCallback(async () => {
    try {
      const res = await api.dashboard();
      setData(res);
      setLoadError('');
    } catch (err) {
      setLoadError(err?.message || 'Não foi possível carregar os indicadores de relatório.');
    }
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports, liveTick]);

  const semana = data?.analytics?.semana || [];
  const taxaReconhecimento = data?.analytics?.taxaReconhecimentoHoje ?? 100;
  const eventosHoje = data?.analytics?.eventosHoje ?? 0;
  const presentesAl = data?.summary?.entraramHojeAlunos ?? 0;
  const turmaStats = data?.turmaStats || [];

  async function exportarCsv() {
    setExporting(true);
    try {
      await api.downloadReportCsv(de, ate);
      showToast('Relatório CSV exportado com sucesso', 'check');
    } catch (error) {
      showToast(error.message || 'Falha ao exportar relatório', 'triangle');
    } finally {
      setExporting(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Relatórios de frequência</h1>
          <p>Indicadores agregados diretamente no PostgreSQL e exportação para planilha</p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="date" value={de} onChange={e => setDe(e.target.value)} style={{ width: 145 }} title="Data inicial" />
          <input type="date" value={ate} onChange={e => setAte(e.target.value)} style={{ width: 145 }} title="Data final" />
          <button className="btn btn-primary" disabled={exporting} onClick={exportarCsv}>
            <Icon name="chart" size={16} /> {exporting ? 'Exportando...' : 'Exportar CSV'}
          </button>
        </div>
      </div>

      {loadError && (
        <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-danger bg-danger-soft px-4 py-2.5 text-sm text-ink">
          <span>{loadError}</span>
          <button type="button" className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={loadReports}>
            Tentar novamente
          </button>
        </div>
      )}

      <div className="grid-2">
        <div className="card chart-card">
          <h2 className="section-title">Frequência dos últimos 5 dias úteis</h2>
          <div className="bar-row">
            {semana.length ? semana.map(item => (
              <div className="bar-col" key={item.dia} title={`${item.dia}: ${item.presentes} alunos (${item.pct}%)`}>
                <span style={{ fontSize: 11, color: 'var(--ink-soft)' }}>{item.pct}%</span>
                <div className="bar" style={{ height: Math.max(6, item.pct) + '%' }}></div>
                <div className="lab">{item.curto}</div>
              </div>
            )) : <div style={{ color: 'var(--ink-faint)', fontSize: 13 }}>Carregando indicadores...</div>}
          </div>
        </div>

        <div className="card chart-card">
          <h2 className="section-title">Taxa de reconhecimento hoje</h2>
          <div className="ring-wrap">
            <RingChart pct={taxaReconhecimento} />
            <div>
              <div className="ring-num">{taxaReconhecimento}%</div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>
                dos eventos registrados hoje na portaria foram identificados ({presentesAl} alunos presentes / {eventosHoje} eventos hoje)
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <h2 className="section-title">Comparativo de hoje entre turmas</h2>
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Turma</th><th>Alunos ativos</th><th>Presentes hoje</th><th>Frequência</th><th>Atrasos hoje</th></tr>
              </thead>
              <tbody>
                {turmaStats.map(t => (
                  <tr key={t.turma}>
                    <td><strong>{t.turma}</strong></td>
                    <td>{t.alunosAtivos}</td>
                    <td>{t.presentesHoje}</td>
                    <td>{t.pct}%</td>
                    <td>{t.atrasosHoje}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

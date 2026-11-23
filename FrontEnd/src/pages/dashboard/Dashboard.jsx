import { useCallback, useEffect, useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import { SevIcon, AlertStatusPill } from '../../components/Pills.jsx';
import { api } from '../../lib/api.js';
import FeedCard from './FeedCard.jsx';

function saudacaoPorHora() {
  const h = new Date().getHours();
  if (h < 12) return 'Bom dia';
  if (h < 18) return 'Boa tarde';
  return 'Boa noite';
}

function dataHojeFormatada() {
  return new Date().toLocaleDateString('pt-BR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
}

export default function Dashboard({ user, liveTick, onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const loadDashboard = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await api.dashboard();
      setData(res);
      setLoadError('');
    } catch (err) {
      setLoadError(err?.message || 'Não foi possível carregar o resumo do painel.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard(Boolean(data));
  }, [liveTick, loadDashboard]);

  const summary = data?.summary || {
    alunosAtivos: 0,
    funcionariosAtivos: 0,
    naEscolaAlunos: 0,
    ausentesHojeAlunos: 0,
    atrasosHojeAlunos: 0,
    presentesHojeFuncionarios: 0,
    atrasosHojeFuncionarios: 0,
    alertasAtivos: 0,
  };
  const turmaStats = data?.turmaStats || [];
  const recentes = data?.recentes || [];
  const abertos = data?.abertos || [];
  const dispositivos = data?.dispositivos || [];
  const camerasOnline = dispositivos.filter(d => d.online).length;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>{saudacaoPorHora()}, {user?.nome?.split(' ')[0] || 'Coordenação'}</h1>
          <p style={{ textTransform: 'capitalize' }}>
            {dataHojeFormatada()} · {camerasOnline}/{dispositivos.length} câmeras de portaria online
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('cadastro')}>
          <Icon name="userplus" size={16} /> Novo cadastro
        </button>
      </div>

      {loadError && (
        <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-danger bg-danger-soft px-4 py-2.5 text-sm text-ink">
          <span>{loadError}</span>
          <button type="button" className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => loadDashboard(false)}>
            Tentar novamente
          </button>
        </div>
      )}

      <div className="stat-grid">
        <div className="card stat-card">
          <div className="k">Na escola agora</div>
          <div className="v">
            {loading && !data ? '—' : summary.naEscolaAlunos}
            <span style={{ fontSize: 15, color: 'var(--ink-faint)' }}>/{summary.alunosAtivos}</span>
          </div>
          <div className="d"><span className="dot" style={{ background: 'var(--good)' }}></span>Entrada automática passiva</div>
        </div>
        <div className="card stat-card">
          <div className="k">Atrasos hoje (alunos)</div>
          <div className="v">{loading && !data ? '—' : summary.atrasosHojeAlunos}</div>
          <div className="d"><span className="dot" style={{ background: 'var(--warn)' }}></span>Entradas após o limite</div>
        </div>
        <div className="card stat-card">
          <div className="k">Ausências hoje (alunos)</div>
          <div className="v">{loading && !data ? '—' : summary.ausentesHojeAlunos}</div>
          <div className="d"><span className="dot" style={{ background: 'var(--danger)' }}></span>Sem registro de entrada hoje</div>
        </div>
        <div className="card stat-card">
          <div className="k">Alertas ativos</div>
          <div className="v">{loading && !data ? '—' : summary.alertasAtivos}</div>
          <div className="d"><span className="dot" style={{ background: 'var(--info)' }}></span>Aguardando análise</div>
        </div>
      </div>

      <div className="section">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span className="inline-block h-[7px] w-[7px] rounded-full bg-good animate-pulse-dot" />
          <h2 className="section-title" style={{ margin: 0 }}>Passagens recentes na portaria</h2>
        </div>
        {recentes.length ? (
          <div className="feed-strip">
            {recentes.map(l => <FeedCard key={l.id} log={l} />)}
          </div>
        ) : (
          <div className="card empty">Nenhuma passagem registrada ainda.</div>
        )}
      </div>

      <div className="grid-2">
        <div className="section" style={{ marginBottom: 0 }}>
          <h2 className="section-title">Frequência de hoje por turma</h2>
          <div className="card">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Turma</th><th>Alunos</th><th>Presentes</th><th>Ausentes</th><th>Frequência</th></tr>
                </thead>
                <tbody>
                  {turmaStats.map(t => (
                    <tr key={t.turma}>
                      <td><strong>{t.turma}</strong></td>
                      <td>{t.alunosAtivos}</td>
                      <td>{t.presentesHoje}</td>
                      <td>{t.ausentesHoje}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ flex: 1, height: 6, borderRadius: 4, background: 'var(--surface-alt)', overflow: 'hidden' }}>
                            <div style={{ width: t.pct + '%', height: '100%', background: 'var(--good)' }}></div>
                          </div>
                          <span style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{t.pct}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div>
          <div className="section" style={{ marginBottom: 16 }}>
            <h2 className="section-title">Equipe hoje</h2>
            <div className="card stat-grid small" style={{ padding: 16 }}>
              <div className="stat-card" style={{ padding: 0 }}>
                <div className="k">Presentes</div>
                <div className="v" style={{ fontSize: 22 }}>
                  {summary.presentesHojeFuncionarios}
                  <span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>/{summary.funcionariosAtivos}</span>
                </div>
              </div>
              <div className="stat-card" style={{ padding: 0 }}>
                <div className="k">Atrasos</div>
                <div className="v" style={{ fontSize: 22 }}>{summary.atrasosHojeFuncionarios}</div>
              </div>
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 10, width: '100%', justifyContent: 'center' }} onClick={() => onNavigate('funcionarios')}>
              Ver funcionários
            </button>
          </div>

          <div className="section" style={{ marginBottom: 0 }}>
            <h2 className="section-title">Alertas em aberto</h2>
            <div className="card" style={{ padding: '6px 14px' }}>
              {abertos.length ? abertos.map(a => (
                <div key={a.id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                  <SevIcon sev={a.severidade} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <strong style={{ fontSize: 13, display: 'block' }}>{a.tipo}</strong>
                    <span style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{a.personName || 'Não identificado'}</span>
                  </div>
                  <AlertStatusPill status={a.status} />
                </div>
              )) : <div className="empty" style={{ padding: 24 }}>Nenhum alerta em aberto agora.</div>}
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 10, width: '100%', justifyContent: 'center' }} onClick={() => onNavigate('alertas')}>
              Ver todos os alertas
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

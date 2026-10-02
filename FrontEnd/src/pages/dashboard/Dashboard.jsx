import Icon from '../../icons/Icon.jsx';
import { SevIcon, AlertStatusPill } from '../../components/Pills.jsx';
import { TURMAS } from '../../data/seed.js';
import FeedCard from './FeedCard.jsx';

export default function Dashboard({ people, logs, alerts, onNavigate }) {
  const alunos = people.filter(p => p.tipo === 'aluno' && p.status === 'ativo');
  const funcionarios = people.filter(p => p.tipo === 'funcionario' && p.status === 'ativo');
  const presentesAl = new Set(logs.filter(l => l.tipo === 'entrada' && l.personId).map(l => l.personId).filter(id => {
    const p = people.find(x => x.id === id); return p && p.tipo === 'aluno';
  }));
  const presentesFunc = new Set(logs.filter(l => l.tipo === 'entrada' && l.personId).map(l => l.personId).filter(id => {
    const p = people.find(x => x.id === id); return p && p.tipo === 'funcionario';
  }));
  const atrasosAl = logs.filter(l => l.status === 'atraso' && l.personId && people.find(p => p.id === l.personId && p.tipo === 'aluno')).length;
  const atrasosFunc = logs.filter(l => l.status === 'atraso' && l.personId && people.find(p => p.id === l.personId && p.tipo === 'funcionario')).length;
  const ausentesAl = alunos.length - presentesAl.size;
  const alertasAtivos = alerts.filter(a => a.status !== 'resolvido').length;
  const recentes = logs.slice(-8).reverse();
  const abertos = alerts.filter(a => a.status !== 'resolvido').slice(0, 3);

  const turmaRows = TURMAS.map(t => {
    const alunosT = alunos.filter(x => x.grupo === t);
    const presentesT = alunosT.filter(x => logs.some(l => l.personId === x.id && l.tipo === 'entrada'));
    const pct = alunosT.length ? Math.round(presentesT.length / alunosT.length * 100) : 0;
    return (
      <tr key={t}>
        <td><strong>{t}</strong></td><td>{alunosT.length}</td><td>{presentesT.length}</td>
        <td>{alunosT.length - presentesT.length}</td>
        <td>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ flex: 1, height: 6, borderRadius: 4, background: 'var(--surface-alt)', overflow: 'hidden' }}>
              <div style={{ width: pct + '%', height: '100%', background: 'var(--good)' }}></div>
            </div>
            <span style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{pct}%</span>
          </div>
        </td>
      </tr>
    );
  });

  return (
    <div>
      <div className="page-head">
        <div><h1>Bom dia, Marina</h1><p>Segunda-feira, 15 de setembro — visão geral de hoje</p></div>
        <button className="btn btn-primary" onClick={() => onNavigate('cadastro')}><Icon name="userplus" size={16} /> Novo cadastro</button>
      </div>

      <div className="stat-grid">
        <div className="card stat-card"><div className="k">Alunos presentes</div>
          <div className="v">{presentesAl.size}<span style={{ fontSize: 15, color: 'var(--ink-faint)' }}>/{alunos.length}</span></div>
          <div className="d"><span className="dot" style={{ background: 'var(--good)' }}></span>Reconhecimento facial na portaria</div></div>
        <div className="card stat-card"><div className="k">Atrasos (alunos)</div><div className="v">{atrasosAl}</div>
          <div className="d"><span className="dot" style={{ background: 'var(--warn)' }}></span>Entradas após o limite</div></div>
        <div className="card stat-card"><div className="k">Ausências (alunos)</div><div className="v">{ausentesAl}</div>
          <div className="d"><span className="dot" style={{ background: 'var(--danger)' }}></span>Sem registro de entrada hoje</div></div>
        <div className="card stat-card"><div className="k">Alertas ativos</div><div className="v">{alertasAtivos}</div>
          <div className="d"><span className="dot" style={{ background: 'var(--info)' }}></span>Aguardando análise</div></div>
      </div>

      <div className="section">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span className="live-dot"></span><h2 className="section-title" style={{ margin: 0 }}>Reconhecimentos recentes</h2>
        </div>
        <div className="feed-strip">{recentes.map(l => <FeedCard key={l.id} log={l} people={people} />)}</div>
      </div>

      <div className="grid-2">
        <div className="section" style={{ marginBottom: 0 }}>
          <h2 className="section-title">Frequência por turma</h2>
          <div className="card"><div className="table-wrap"><table>
            <thead><tr><th>Turma</th><th>Alunos</th><th>Presentes</th><th>Ausentes</th><th>Frequência</th></tr></thead>
            <tbody>{turmaRows}</tbody>
          </table></div></div>
        </div>
        <div>
          <div className="section" style={{ marginBottom: 16 }}>
            <h2 className="section-title">Equipe hoje</h2>
            <div className="card stat-grid small" style={{ padding: 16 }}>
              <div className="stat-card" style={{ padding: 0 }}><div className="k">Presentes</div>
                <div className="v" style={{ fontSize: 22 }}>{presentesFunc.size}<span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>/{funcionarios.length}</span></div></div>
              <div className="stat-card" style={{ padding: 0 }}><div className="k">Atrasos</div>
                <div className="v" style={{ fontSize: 22 }}>{atrasosFunc}</div></div>
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 10, width: '100%', justifyContent: 'center' }} onClick={() => onNavigate('funcionarios')}>Ver funcionários</button>
          </div>
          <div className="section" style={{ marginBottom: 0 }}>
            <h2 className="section-title">Alertas em aberto</h2>
            <div className="card" style={{ padding: '6px 14px' }}>
              {abertos.length ? abertos.map(a => {
                const p = a.personId ? people.find(x => x.id === a.personId) : null;
                return (
                  <div key={a.id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                    <SevIcon sev={a.severidade} />
                    <div style={{ flex: 1, minWidth: 0 }}><strong style={{ fontSize: 13, display: 'block' }}>{a.tipo}</strong>
                      <span style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{p ? p.nome : 'Não identificado'}</span></div>
                    <AlertStatusPill status={a.status} />
                  </div>
                );
              }) : <div className="empty" style={{ padding: 24 }}>Nenhum alerta em aberto agora.</div>}
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 10, width: '100%', justifyContent: 'center' }} onClick={() => onNavigate('alertas')}>Ver todos os alertas</button>
          </div>
        </div>
      </div>
    </div>
  );
}

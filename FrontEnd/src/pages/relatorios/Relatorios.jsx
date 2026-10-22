import RingChart from '../../components/RingChart.jsx';
import { mulberry32, TURMAS } from '../../data/seed.js';

export default function Relatorios({ people, logs }) {
  const dias = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex'];
  const rf = mulberry32(55);
  const valores = dias.map(() => 78 + Math.floor(rf() * 18));
  const taxaReconhecimento = Math.round((logs.filter(l => l.status !== 'nao-reconhecido').length / logs.length) * 100);
  const alunos = people.filter(p => p.tipo === 'aluno' && p.status === 'ativo');
  const presentesAl = alunos.filter(x => logs.some(l => l.personId === x.id && l.tipo === 'entrada')).length;

  const turmaRows = TURMAS.map(t => {
    const alunosT = alunos.filter(x => x.grupo === t);
    const presentesT = alunosT.filter(x => logs.some(l => l.personId === x.id && l.tipo === 'entrada'));
    const atrasosT = alunosT.filter(x => logs.some(l => l.personId === x.id && l.status === 'atraso'));
    const pct = alunosT.length ? Math.round(presentesT.length / alunosT.length * 100) : 0;
    return <tr key={t}><td><strong>{t}</strong></td><td>{alunosT.length}</td><td>{pct}%</td><td>{atrasosT.length}</td></tr>;
  });

  return (
    <div>
      <div className="page-head"><div><h1>Relatórios</h1><p>Indicadores de frequência e reconhecimento facial</p></div></div>
      <div className="grid-2">
        <div className="card chart-card"><h2 className="section-title">Frequência da semana</h2>
          <div className="bar-row">{dias.map((d, i) => (
            <div className="bar-col" key={d}><div className="bar" style={{ height: (valores[i]) + '%' }}></div><div className="lab">{d}</div></div>
          ))}</div>
        </div>
        <div className="card chart-card"><h2 className="section-title">Taxa de reconhecimento</h2>
          <div className="ring-wrap"><RingChart pct={taxaReconhecimento} />
            <div><div className="ring-num">{taxaReconhecimento}%</div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>das tentativas na portaria foram reconhecidas automaticamente hoje ({presentesAl} de {logs.length} eventos)</div></div>
          </div>
        </div>
      </div>
      <div className="section"><h2 className="section-title">Comparativo entre turmas</h2>
        <div className="card"><div className="table-wrap"><table>
          <thead><tr><th>Turma</th><th>Alunos</th><th>Frequência</th><th>Atrasos hoje</th></tr></thead>
          <tbody>{turmaRows}</tbody>
        </table></div></div>
      </div>
    </div>
  );
}

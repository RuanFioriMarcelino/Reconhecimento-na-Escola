import { useState } from 'react';
import AlertCard from './AlertCard.jsx';

export default function Alertas({ people, alerts, onResolver }) {
  const [status, setStatus] = useState('');
  const lista = alerts.filter(a => !status || a.status === status);
  const abertos = alerts.filter(a => a.status !== 'resolvido').length;
  return (
    <div>
      <div className="page-head"><div><h1>Alertas</h1><p>{abertos} alertas aguardando atenção da coordenação</p></div></div>
      <div className="filters">
        <select value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">Todos os status</option><option value="novo">Novo</option>
          <option value="em-analise">Em análise</option><option value="resolvido">Resolvido</option>
        </select>
      </div>
      {lista.length ? lista.map(a => <AlertCard key={a.id} alert={a} people={people} onResolver={onResolver} />)
        : <div className="card empty">Nenhum alerta para esse filtro.</div>}
    </div>
  );
}

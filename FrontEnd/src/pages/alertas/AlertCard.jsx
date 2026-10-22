import { SevIcon, AlertStatusPill } from '../../components/Pills.jsx';

export default function AlertCard({ alert, people, onResolver }) {
  const p = alert.personId ? people.find(x => x.id === alert.personId) : null;
  return (
    <div className={"alert-card sev-" + alert.severidade}>
      <SevIcon sev={alert.severidade} />
      <div className="at">
        <strong>{alert.tipo}</strong>
        <p>{p ? <>{p.nome} · {p.grupo}</> : 'Não identificado'} — {alert.descricao}</p>
      </div>
      <div className="aa">
        <AlertStatusPill status={alert.status} />
        {onResolver && alert.status !== 'resolvido' &&
          <button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => onResolver(alert.id)}>Marcar resolvido</button>}
      </div>
    </div>
  );
}

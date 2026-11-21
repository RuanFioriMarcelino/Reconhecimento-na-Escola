import Avatar from '../../components/Avatar.jsx';
import { LogStatusPill } from '../../components/Pills.jsx';
import { fmtMin } from '../../data/seed.js';

export default function FeedCard({ log }) {
  const nome = log.personName || 'Rosto não identificado';
  const dirLabel = log.tipo === 'entrada' ? 'Entrada' : 'Saída';
  const sub = `${log.personGrupo || log.local} · ${dirLabel}`;
  const confText = log.confianca != null ? ` · ${Math.round(log.confianca * 100)}%` : '';

  return (
    <div className="feed-card">
      <div className="top">
        <Avatar nome={nome} size={34} />
        <div>
          <div className="name">{nome}</div>
          <div className="sub">{sub}</div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
        <span className="time">{fmtMin(log.horaMin)}{confText}</span>
        <LogStatusPill status={log.status} />
      </div>
    </div>
  );
}

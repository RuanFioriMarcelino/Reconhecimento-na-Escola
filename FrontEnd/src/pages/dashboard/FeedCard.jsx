import Avatar from '../../components/Avatar.jsx';
import { LogStatusPill } from '../../components/Pills.jsx';
import { fmtMin } from '../../data/seed.js';

export default function FeedCard({ log, people }) {
  const p = log.personId ? people.find(x => x.id === log.personId) : null;
  const nome = p ? p.nome : 'Rosto não identificado';
  const sub = p ? p.grupo : log.local;
  return (
    <div className="feed-card">
      <div className="top">
        <Avatar nome={nome} size={34} />
        <div><div className="name">{nome}</div><div className="sub">{sub}</div></div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="time">{fmtMin(log.horaMin)}</span>
        <LogStatusPill status={log.status} />
      </div>
    </div>
  );
}

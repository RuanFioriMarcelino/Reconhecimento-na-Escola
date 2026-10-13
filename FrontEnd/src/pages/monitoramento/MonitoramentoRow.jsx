import Avatar from '../../components/Avatar.jsx';
import { TipoPill, LogStatusPill } from '../../components/Pills.jsx';
import { fmtMin } from '../../data/seed.js';

/* padding/alinhamento uniformes para todas as células */
const TD = 'px-3 py-[11px] align-middle';

export default function MonitoramentoRow({ log, people, onNavigate }) {
  const p = log.personId ? people.find(x => x.id === log.personId) : null;
  const nome = p ? p.nome : 'Rosto não identificado';

  return (
    <tr
      className={p ? 'cursor-pointer hover:bg-surface-alt' : ''}
      onClick={() => p && onNavigate('pessoa', p.tipo, p.id)}
    >
      <td className={TD + ' font-mono'}>{fmtMin(log.horaMin)}</td>
      <td className={TD}>
        <div className="flex items-center gap-2.5">
          <Avatar nome={nome} size={28} />
          {nome}
        </div>
      </td>
      <td className={TD}>{p ? <TipoPill tipo={p.tipo} /> : '—'}</td>
      <td className={TD}>{p ? p.grupo : '—'}</td>
      <td className={TD}>{log.tipo === 'entrada' ? 'Entrada' : 'Saída'}</td>
      <td className={TD}>
        <LogStatusPill status={log.status} />
      </td>
    </tr>
  );
}

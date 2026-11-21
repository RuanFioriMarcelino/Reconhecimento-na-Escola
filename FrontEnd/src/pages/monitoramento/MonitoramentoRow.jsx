import Avatar from '../../components/Avatar.jsx';
import { TipoPill, LogStatusPill } from '../../components/Pills.jsx';
import { fmtMin } from '../../data/seed.js';

const TD = 'px-3 py-[11px] align-middle';

export default function MonitoramentoRow({ log, onNavigate }) {
  const nome = log.personName || 'Rosto não identificado';
  const conf = log.confianca != null ? `${Math.round(log.confianca * 100)}%` : '—';
  const hasPerson = Boolean(log.personId && log.personType);

  return (
    <tr
      className={hasPerson ? 'cursor-pointer hover:bg-surface-alt' : ''}
      onClick={() => hasPerson && onNavigate('pessoa', log.personType, log.personId)}
    >
      <td className={TD + ' font-mono text-xs'}>
        {log.dataDia ? `${log.dataDia} ` : ''}{fmtMin(log.horaMin)}
      </td>
      <td className={TD}>
        <div className="flex items-center gap-2.5">
          <Avatar nome={nome} size={28} />
          <span>{nome}</span>
        </div>
      </td>
      <td className={TD}>{log.personType ? <TipoPill tipo={log.personType} /> : '—'}</td>
      <td className={TD}>{log.personGrupo || '—'}</td>
      <td className={TD}>{log.tipo === 'entrada' ? 'Entrada' : 'Saída'}</td>
      <td className={TD + ' text-xs text-ink-soft'}>{log.local}</td>
      <td className={TD + ' font-mono text-xs'}>{conf}</td>
      <td className={TD}>
        <LogStatusPill status={log.status} />
      </td>
    </tr>
  );
}

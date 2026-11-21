import { SevIcon, AlertStatusPill } from '../../components/Pills.jsx';

export default function AlertCard({ alert, onUpdateStatus }) {
  const criado = alert.criadoEm
    ? new Date(alert.criadoEm).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
    : '';

  return (
    <div className={'alert-card sev-' + alert.severidade}>
      <SevIcon sev={alert.severidade} />
      <div className="at">
        <strong>{alert.tipo}</strong>
        <p>
          {alert.personName ? <>{alert.personName} · {alert.personGrupo}</> : 'Não identificado'} — {alert.descricao}
        </p>
        <div style={{ fontSize: 11.5, color: 'var(--ink-faint)', marginTop: 4 }}>
          {criado && <span>Gerado em {criado}</span>}
          {alert.status === 'resolvido' && alert.resolvidoPor && (
            <span> · Resolvido por {alert.resolvidoPor}</span>
          )}
        </div>
      </div>
      <div className="aa">
        <AlertStatusPill status={alert.status} />
        {onUpdateStatus && alert.status !== 'resolvido' && (
          <div style={{ display: 'flex', gap: 6 }}>
            {alert.status === 'novo' && (
              <button
                className="btn btn-ghost"
                style={{ padding: '5px 10px', fontSize: 12 }}
                onClick={() => onUpdateStatus(alert.id, 'em-analise')}
              >
                Analisar
              </button>
            )}
            <button
              className="btn btn-ghost"
              style={{ padding: '5px 10px', fontSize: 12 }}
              onClick={() => onUpdateStatus(alert.id, 'resolvido')}
            >
              Resolver
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

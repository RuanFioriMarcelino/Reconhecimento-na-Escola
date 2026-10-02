import Icon from '../icons/Icon.jsx';

export function LogStatusPill({ status }) {
  if (status === 'atraso') return <span className="pill pill-warn"><Icon name="clock" size={12} /> Atraso</span>;
  if (status === 'nao-reconhecido') return <span className="pill pill-danger"><Icon name="triangle" size={12} /> Não reconhecido</span>;
  return <span className="pill pill-good"><Icon name="check" size={12} /> Reconhecido</span>;
}

export function AlertStatusPill({ status }) {
  if (status === 'novo') return <span className="pill pill-danger">Novo</span>;
  if (status === 'em-analise') return <span className="pill pill-warn">Em análise</span>;
  return <span className="pill pill-good">Resolvido</span>;
}

export function TipoPill({ tipo }) {
  return tipo === 'funcionario'
    ? <span className="pill pill-info"><Icon name="briefcase" size={11} /> Funcionário</span>
    : <span className="pill pill-neutral"><Icon name="users" size={11} /> Aluno</span>;
}

export function SevIcon({ sev }) {
  const bg = sev === 'alta' ? 'var(--danger-soft)' : sev === 'media' ? 'var(--warn-soft)' : 'var(--info-soft)';
  const fg = sev === 'alta' ? 'var(--danger)' : sev === 'media' ? 'var(--warn)' : 'var(--info)';
  return <div className="ai" style={{ background: bg, color: fg }}><Icon name="triangle" size={16} /></div>;
}

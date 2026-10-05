import { useState } from 'react';
import Icon from '../../icons/Icon.jsx';
import Avatar from '../../components/Avatar.jsx';
import Button from '../../components/ui/Button.jsx';
import { cx } from '../../lib/cx.js';
import { PERSON_CONFIG } from '../../data/seed.js';

/* base compartilhada entre search-input e select */
const FIELD_BASE =
  'rounded-[7px] border border-line bg-surface font-body text-[13.5px] ' +
  'leading-[normal] text-ink focus:border-primary focus:outline-none';

/* busca: padding-left generoso para o ícone; padding-right/top/bottom normais */
const SEARCH_INPUT = cx(FIELD_BASE, 'w-full pl-[34px] pr-3 py-[9px]');

/* select: padding uniforme + largura máxima */
const SELECT = cx(FIELD_BASE, 'w-full max-w-[190px] px-3 py-[9px]');

export default function PeopleList({ tipo, people, onNavigate }) {
  const cfg = PERSON_CONFIG[tipo];
  const [busca, setBusca] = useState('');
  const [grupo, setGrupo] = useState('');

  const lista = people.filter(
    p =>
      p.tipo === tipo &&
      (!busca ||
        p.nome.toLowerCase().includes(busca.toLowerCase()) ||
        p.documento.toLowerCase().includes(busca.toLowerCase())) &&
      (!grupo || p.grupo === grupo),
  );

  return (
    <div>
      {/* cabeçalho */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display m-0 mb-1 text-[23px] font-semibold">{cfg.plural}</h1>
          <p className="m-0 text-sm text-ink-soft">
            {people.filter(p => p.tipo === tipo).length}{' '}
            {cfg.plural.toLowerCase()} cadastrados no reconhecimento facial
          </p>
        </div>
        <Button variant="primary" onClick={() => onNavigate('cadastro', tipo)}>
          <Icon name="userplus" size={16} /> Novo cadastro
        </Button>
      </div>

      {/* filtros */}
      <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
        {/* campo de busca */}
        <div className="relative min-w-[230px] flex-1">
          <Icon
            name="search"
            size={16}
            className="pointer-events-none absolute left-[11px] top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <input
            className={SEARCH_INPUT}
            placeholder={'Buscar por nome ou ' + cfg.documentoLabel.toLowerCase()}
            value={busca}
            onChange={e => setBusca(e.target.value)}
          />
        </div>
        {/* filtro por grupo */}
        <select className={SELECT} value={grupo} onChange={e => setGrupo(e.target.value)}>
          <option value="">{'Todos: ' + cfg.grupoLabel.toLowerCase()}</option>
          {cfg.grupoOptions.map(g => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      </div>

      {/* grid de cartões */}
      {lista.length ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-3">
          {lista.map(p => (
            <button
              key={p.id}
              className="flex cursor-pointer items-start gap-3 rounded-lg border border-line bg-surface p-3.5 text-left shadow transition-colors hover:border-primary"
              onClick={() => onNavigate('pessoa', tipo, p.id)}
            >
              <Avatar nome={p.nome} size={44} />
              <div>
                <strong className="mb-0.5 block text-[13.5px] font-semibold">{p.nome}</strong>
                <div className="mb-2 text-xs text-ink-faint">
                  {p.grupo} · {cfg.documentoLabel} {p.documento}
                </div>
                {p.status === 'inativo' ? (
                  <span className="pill pill-neutral">Inativo</span>
                ) : (
                  <span className="pill pill-good">
                    <Icon name="check" size={11} /> Rosto cadastrado
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2.5 rounded-lg border border-line bg-surface px-5 py-10 text-center text-ink-faint shadow">
          <Icon name={cfg.icon} size={30} className="opacity-60" />
          <div>Nenhum registro encontrado para esse filtro.</div>
        </div>
      )}
    </div>
  );
}

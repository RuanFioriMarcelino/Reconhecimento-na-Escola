import Icon from '../icons/Icon.jsx';
import { NAV } from '../router/useHashRoute.js';
import { cx } from '../lib/cx.js';
import { initials } from '../data/seed.js';

const ITEM =
  'flex w-full cursor-pointer items-center gap-[11px] rounded-[7px] border-0 px-3 py-[9px] text-left text-sm leading-[normal]';
const ITEM_NORMAL = 'bg-transparent font-medium text-ink-soft hover:bg-surface-alt hover:text-ink';
const ITEM_ATIVO = 'bg-primary-soft font-semibold text-primary-strong';

const PAPEL_LABEL = {
  admin: 'Administração',
  coordenacao: 'Coordenação pedagógica',
  secretaria: 'Secretaria escolar',
  visualizador: 'Visualizador',
};

export default function Sidebar({ user, view, open, openAlertsCount = 0, onNavigate, onLogout }) {
  const nome = user?.nome || 'Usuário';
  const papelLabel = PAPEL_LABEL[user?.papel] || 'Coordenação';

  return (
    <aside
      className={cx(
        'fixed inset-y-0 left-0 z-50 flex w-60 shrink-0 flex-col overflow-y-auto border-r border-line bg-surface',
        'transition-transform duration-200 ease-out',
        'shadow-[0_0_30px_rgba(0,0,0,.25)] nav:translate-x-0 nav:shadow-none',
        open ? 'translate-x-0' : '-translate-x-full'
      )}
    >
      <div className="flex items-center gap-2.5 border-b border-line px-[18px] pt-5 pb-4">
        <div className="flex size-[34px] shrink-0 items-center justify-center rounded-lg bg-primary text-white">
          <Icon name="scan" size={19} />
        </div>
        <div className="flex flex-col leading-[1.15]">
          <strong className="font-display text-[15px] font-semibold">Reconhece+ v2</strong>
          <span className="text-[11.5px] text-ink-faint">Gestão escolar</span>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 px-2.5 py-3.5">
        {NAV.map(n => (
          <button
            key={n.id}
            className={cx(ITEM, view === n.id ? ITEM_ATIVO : ITEM_NORMAL)}
            onClick={() => onNavigate(n.id)}
          >
            <Icon name={n.icon} size={17} />
            <span className="flex-1">{n.label}</span>
            {n.id === 'alertas' && openAlertsCount > 0 && (
              <span className="rounded-full bg-danger px-1.5 py-0.5 text-[10.5px] font-bold leading-none text-white">
                {openAlertsCount > 99 ? '99+' : openAlertsCount}
              </span>
            )}
          </button>
        ))}
      </nav>

      <div className="border-t border-line px-2.5 pt-3 pb-4">
        <div className="mb-1 flex items-center gap-2.5 rounded-[7px] px-2.5 py-2">
          <div className="flex size-[30px] shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
            {initials(nome)}
          </div>
          <div className="min-w-0 leading-[1.2]">
            <strong className="block truncate text-[13px]">{nome}</strong>
            <span className="text-[11.5px] text-ink-faint">{papelLabel}</span>
          </div>
        </div>
        <button className={cx(ITEM, ITEM_NORMAL)} onClick={onLogout}>
          <Icon name="logout" size={17} />
          <span>Sair</span>
        </button>
      </div>
    </aside>
  );
}

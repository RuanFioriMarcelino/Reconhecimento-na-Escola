import Icon from '../icons/Icon.jsx';

// barra superior com o botão do menu — só existe em telas estreitas
export default function Topbar({ title, onToggle }) {
  return (
    <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-surface px-4 py-3.5 nav:hidden">
      <button
        aria-label="Abrir menu"
        onClick={onToggle}
        className="flex size-9 cursor-pointer items-center justify-center rounded-[7px] border border-line bg-transparent text-ink"
      >
        <Icon name="menu" size={18} />
      </button>
      <span className="font-display text-[15px] font-semibold">{title}</span>
    </div>
  );
}

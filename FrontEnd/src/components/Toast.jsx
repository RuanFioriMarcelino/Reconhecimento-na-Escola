import Icon from '../icons/Icon.jsx';
import { cx } from '../lib/cx.js';

// aviso rápido no rodapé da tela. `toast` = { msg, icon } ou null
export default function Toast({ toast }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cx(
        'pointer-events-none fixed bottom-[22px] left-1/2 z-100 flex -translate-x-1/2 items-center gap-[9px]',
        'rounded-lg bg-ink px-[18px] py-[11px] text-[13.5px] text-bg shadow-[0_6px_20px_rgba(0,0,0,.25)]',
        'transition duration-250 ease-out',
        toast ? 'translate-y-0 opacity-100' : 'translate-y-5 opacity-0'
      )}
    >
      {toast && (
        <>
          {toast.icon && <Icon name={toast.icon} size={15} />}
          <span>{toast.msg}</span>
        </>
      )}
    </div>
  );
}

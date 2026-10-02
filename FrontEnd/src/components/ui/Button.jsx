import { cx } from '../../lib/cx.js';

const BASE =
  'inline-flex cursor-pointer items-center gap-2 whitespace-nowrap rounded-[7px] border px-4 py-[9px] ' +
  'font-body text-[13.5px] font-semibold leading-[normal] disabled:cursor-not-allowed disabled:opacity-50';

// classes completas (nada de montar nome de classe por concatenação — o Tailwind não enxergaria)
const VARIANTES = {
  primary: 'border-transparent bg-primary text-white hover:bg-primary-strong',
  ghost: 'border-line bg-surface text-ink hover:bg-surface-alt',
  dangerGhost: 'border-danger bg-surface text-danger',
};

/**
 * Botão padrão do sistema.
 * variant: 'primary' | 'ghost' | 'dangerGhost'   block: ocupa a largura toda
 * Atenção: o type padrão é "button" (e não "submit"); passe type="submit" nos formulários.
 */
export default function Button({ variant = 'primary', block = false, type = 'button', className, ...props }) {
  return (
    <button
      type={type}
      className={cx(BASE, VARIANTES[variant], block && 'w-full justify-center', className)}
      {...props}
    />
  );
}

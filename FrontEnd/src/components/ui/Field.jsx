import { cx } from '../../lib/cx.js';

/** Rótulo + controle. O <label> envolve o campo, então clicar no texto foca o input. */
export function Field({ label, className, children }) {
  return (
    <label className={cx('block', className)}>
      <span className="mb-1.5 block text-[12.5px] font-semibold text-ink-soft">{label}</span>
      {children}
    </label>
  );
}

const INPUT =
  'w-full rounded-[7px] border border-line bg-surface px-3 py-[9px] font-body text-[13.5px] leading-[normal] text-ink focus:border-primary';

export function Input({ className, ...props }) {
  return <input className={cx(INPUT, className)} {...props} />;
}

export default function ToggleRow({ title, desc, on, onToggle, disabled = false }) {
  return (
    <div className="toggle-row">
      <div className="tt"><strong>{title}</strong><span>{desc}</span></div>
      <button
        type="button"
        disabled={disabled}
        aria-pressed={Boolean(on)}
        aria-label={title}
        className={"switch" + (on ? ' on' : '')}
        style={disabled ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
        onClick={() => { if (!disabled && onToggle) onToggle(); }}
      />
    </div>
  );
}

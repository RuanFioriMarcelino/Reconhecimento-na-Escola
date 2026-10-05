export default function RingChart({ pct }) {
  const r = 42, c = 2 * Math.PI * r, off = c - (pct / 100) * c;
  return (
    <svg width="100" height="100" viewBox="0 0 100 100">
      <circle cx="50" cy="50" r={r} fill="none" stroke="var(--surface-alt)" strokeWidth="10" />
      <circle
        cx="50" cy="50" r={r} fill="none" stroke="var(--good)" strokeWidth="10"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off}
        transform="rotate(-90 50 50)"
      />
    </svg>
  );
}

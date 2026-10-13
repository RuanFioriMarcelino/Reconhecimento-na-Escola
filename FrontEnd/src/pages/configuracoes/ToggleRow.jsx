export default function ToggleRow({ title, desc, on, onToggle }) {
  return (
    <div className="toggle-row">
      <div className="tt"><strong>{title}</strong><span>{desc}</span></div>
      <button className={"switch" + (on ? ' on' : '')} onClick={onToggle}></button>
    </div>
  );
}

const ICON_PATHS = {
  grid: '<rect x="3.2" y="3.2" width="7" height="7" rx="1.5"/><rect x="13.8" y="3.2" width="7" height="7" rx="1.5"/><rect x="3.2" y="13.8" width="7" height="7" rx="1.5"/><rect x="13.8" y="13.8" width="7" height="7" rx="1.5"/>',
  users: '<circle cx="8.5" cy="8" r="3.1"/><path d="M2.8 19.5c.3-3.4 2.7-5.7 5.7-5.7s5.4 2.3 5.7 5.7"/><circle cx="16.7" cy="8.6" r="2.5"/><path d="M14.9 14.1c2.4.4 4.2 2.2 4.6 5"/>',
  briefcase: '<rect x="3" y="7" width="18" height="12" rx="2"/><path d="M8 7V5.5A2.5 2.5 0 0 1 10.5 3h3A2.5 2.5 0 0 1 16 5.5V7"/><path d="M3 12.5h18"/>',
  camera: '<rect x="2.8" y="7" width="18.4" height="13" rx="2.2"/><path d="M8.3 7l1.5-2.5h4.4L15.7 7"/><circle cx="12" cy="13.6" r="3.4"/>',
  activity: '<path d="M2.5 12h3.6l2-6.2 4 13 2-6.8h5.4"/>',
  bell: '<path d="M6 10.2a6 6 0 0 1 12 0c0 3.9 1.4 5.3 1.4 5.3H4.6S6 14.1 6 10.2z"/><path d="M10 18.6a2 2 0 0 0 4 0"/>',
  chart: '<rect x="4" y="13" width="4" height="7" fill="currentColor" stroke="none"/><rect x="10" y="7.5" width="4" height="12.5" fill="currentColor" stroke="none"/><rect x="16" y="3.5" width="4" height="16.5" fill="currentColor" stroke="none"/>',
  gear: '<circle cx="12" cy="12" r="3.1"/><circle cx="12" cy="12" r="8" stroke-dasharray="2.6 2.6"/>',
  logout: '<path d="M9.5 4H5.3a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4.2"/><path d="M16 16.5l4.5-4.5L16 7.5"/><path d="M20.3 12H9.8"/>',
  search: '<circle cx="10.6" cy="10.6" r="6.6"/><path d="M20 20l-4.8-4.8"/>',
  back: '<path d="M19 12H5"/><path d="M11.5 18.5L5 12l6.5-6.5"/>',
  check: '<path d="M20 6.4L9.3 17 4 11.8"/>',
  menu: '<path d="M3 6.5h18"/><path d="M3 12h18"/><path d="M3 17.5h18"/>',
  triangle: '<path d="M12 3.4l9.2 16H2.8z"/><path d="M12 9.6v3.8"/><path d="M12 17v.2"/>',
  clock: '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.2V12l3.2 1.9"/>',
  edit: '<path d="M11.5 19.5H20"/><path d="M15.9 4.6a2 2 0 0 1 2.9 2.9L7.4 18.9l-4 .9.9-4L15.9 4.6z"/>',
  userplus: '<circle cx="9" cy="8.2" r="3.4"/><path d="M2.8 19.6c.4-3.6 2.9-6 6.2-6s5.8 2.4 6.2 6"/><path d="M18.5 8v5"/><path d="M16 10.5h5"/>',
  scan: '<path d="M4 8V5.6A1.6 1.6 0 0 1 5.6 4H8"/><path d="M16 4h2.4A1.6 1.6 0 0 1 20 5.6V8"/><path d="M20 16v2.4a1.6 1.6 0 0 1-1.6 1.6H16"/><path d="M8 20H5.6A1.6 1.6 0 0 1 4 18.4V16"/><path d="M6.5 12h11"/>'
};

export default function Icon({ name, size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: ICON_PATHS[name] || '' }}
    />
  );
}

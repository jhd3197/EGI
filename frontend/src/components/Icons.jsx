// Shared line icons (currentColor-driven so callers set color via style).
const base = (size) => ({
  width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round',
})

export const HomeIcon = ({ size = 20 }) => (
  <svg {...base(size)}><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /></svg>
)
export const SearchIcon = ({ size = 20 }) => (
  <svg {...base(size)}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
)
export const SheltersIcon = ({ size = 20 }) => (
  <svg {...base(size)}><path d="M4 21V8l5-3 5 3v13" /><path d="M14 21V11l5 3v7" /><path d="M3 21h18" /></svg>
)
export const MineIcon = ({ size = 20 }) => (
  <svg {...base(size)}><path d="M5 4h14v16l-7-3-7 3z" /></svg>
)
// Concentric broadcast arcs — "Red local" / nearby-devices mesh.
export const MeshIcon = ({ size = 20 }) => (
  <svg {...base(size)}>
    <path d="M5 12.5a9 9 0 0 1 14 0" />
    <path d="M8 15.5a5 5 0 0 1 8 0" />
    <circle cx="12" cy="19" r="1" />
  </svg>
)
// Map pin — geospatial "Mapa" view.
export const MapIcon = ({ size = 20 }) => (
  <svg {...base(size)}>
    <path d="M12 21s-6-5.3-6-10a6 6 0 0 1 12 0c0 4.7-6 10-6 10z" />
    <circle cx="12" cy="11" r="2.2" />
  </svg>
)
// Route / turn-by-turn — offline directions "Cómo llegar" view (plan-21).
export const RouteIcon = ({ size = 20 }) => (
  <svg {...base(size)}>
    <circle cx="6" cy="19" r="2" />
    <circle cx="18" cy="5" r="2" />
    <path d="M8 19h6a4 4 0 0 0 0-8H10a4 4 0 0 1 0-8h6" />
  </svg>
)
// Bar chart — operational-intelligence "Panel" / dashboard view.
export const ChartIcon = ({ size = 20 }) => (
  <svg {...base(size)}>
    <path d="M3 21h18" />
    <rect x="5" y="11" width="3.5" height="7" />
    <rect x="10.5" y="7" width="3.5" height="11" />
    <rect x="16" y="13" width="3.5" height="5" />
  </svg>
)

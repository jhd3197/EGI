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

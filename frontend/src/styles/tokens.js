// Design tokens for the EGI PWA (plan-29 §4). A single, minimal source of truth
// for the colors, type scale, spacing rhythm, radii, shadows and z-index the UI
// already uses — extracted from the values that were scattered as inline magic
// numbers across components. The app styles everything with inline CSS strings
// (see lib/css.js), so these are plain JS values you spread or interpolate, not
// a CSS framework. Keep this list small: add a token only when a real value
// repeats. Do not introduce new one-off hex codes in refactored components —
// reach for a token (or add one here) instead.

// ----- Colors -----
// EGI's brand mark is the red cross; red is the single accent. Text is a warm
// near-black; surfaces moved from a warm beige (#F4EFE7) to a clean cool neutral
// in plan-29 so the app no longer reads as a generic AI-app palette.
export const color = {
  // Brand / primary action (the red cross, primary buttons, active accents)
  primary: '#E5343B',
  primaryDark: '#C2272D', // pressed / link-on-light variants (also #B7242A historically)
  // Destructive actions share the brand red on purpose — there is one red.
  danger: '#E5343B',
  // Positive / safe / "accepting" states
  success: '#1B7A45',
  successDark: '#15683A',
  successBg: '#E9F4ED',
  // Text ramp (darkest → lightest)
  text: '#1A1714', // primary ink
  textStrong: '#2A2520',
  textBody: '#4A443D',
  textMuted: '#8A837A', // secondary / captions
  textFaint: '#A9A299', // disabled / monospace meta
  // Surfaces
  bg: '#F8F9FA', // app background — clean cool neutral (was warm beige #F4EFE7)
  surface: '#FFFFFF', // cards, sheets, inputs
  surfaceSunken: '#F1F3F5', // subtle raised/sunken fills (chips, strips) on bg
  // Borders / hairlines
  border: '#E6E2DC',
  borderStrong: '#E2DED8',
}

// ----- Typography -----
export const font = {
  sans: "'IBM Plex Sans', system-ui, sans-serif",
  mono: "'IBM Plex Mono', monospace",
}

// Type scale (px). Matches the sizes already in use across screens.
export const fontSize = {
  xs: 11,
  sm: 12,
  base: 13,
  lg: 15,
  xl: 19,
  '2xl': 22,
  '3xl': 30,
}

export const fontWeight = {
  regular: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
}

// ----- Spacing (4 px rhythm) -----
export const space = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  6: 24,
  8: 32,
  12: 48,
  16: 64,
}

// ----- Radius -----
export const radius = {
  sm: 8,
  md: 11,
  lg: 13,
  pill: 999,
}

// ----- Shadows -----
export const shadow = {
  card: '0 1px 2px rgba(26,23,20,.05)',
  primary: '0 8px 16px -8px rgba(229,52,59,.6)',
}

// ----- Z-index scale -----
export const z = {
  base: 0,
  banner: 10,
  tabbar: 20,
  sheet: 100,
  modal: 200,
}

export default { color, font, fontSize, fontWeight, space, radius, shadow, z }

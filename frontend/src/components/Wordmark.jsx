import { css } from '../lib/css.js'

// The "EGI" wordmark: a large "E" so "Emergencia" reads first, then "GI" smaller.
// All caps. Pass `size` for the cap-height of the "E"; "GI" scales to ~0.6 of it.
export default function Wordmark({ size = 30, color = '#1A1714' }) {
  const small = Math.round(size * 0.6)
  return (
    <span style={{ ...css("display:inline-flex;align-items:baseline;font-family:'IBM Plex Sans';font-weight:700;letter-spacing:-.02em;line-height:1;"), color }}>
      <span style={{ fontSize: size }}>E</span>
      <span style={{ fontSize: small }}>GI</span>
    </span>
  )
}

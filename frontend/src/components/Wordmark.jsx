import { css } from '../lib/css.js'
import { color } from '../styles/tokens.js'

// The "EGI" wordmark. All caps, one uniform size (plan-29 §3.1 removed an earlier
// split that rendered "E" larger than "GI", which looked like a broken logo).
// Pass `size` for the cap-height of the whole wordmark.
export default function Wordmark({ size = 30, color: c = color.text }) {
  return (
    <span style={{ ...css("display:inline-flex;align-items:baseline;font-family:'IBM Plex Sans';font-weight:700;letter-spacing:-.02em;line-height:1;"), color: c, fontSize: size }}>
      EGI
    </span>
  )
}

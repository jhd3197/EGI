import { css } from '../lib/css.js'
import { color } from '../styles/tokens.js'

// The little red EGI cross mark, reused at a few sizes.
export default function Logo({ size = 40, radius = 12, bar = 21, thick = 5 }) {
  return (
    <div style={{ ...css('position:relative;flex:none;'), background: color.primary, width: size, height: size, borderRadius: radius }}>
      <span style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', width: bar, height: thick, background: color.surface, borderRadius: 1.5 }} />
      <span style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', width: thick, height: bar, background: color.surface, borderRadius: 1.5 }} />
    </div>
  )
}

import { css } from '../lib/css.js'

// Subtle indicator shown when the user has hidden one or more content categories
// in Settings (plan-24 Phase 3), e.g. "Showing people and shelters. Animals
// hidden by your settings." Renders nothing when no category is hidden.
export default function CategoryFilterNote({ view }) {
  if (!view.categoryFilterNote) return null
  return (
    <div
      role="note"
      style={css('display:flex;align-items:center;gap:8px;margin:0 0 12px;padding:9px 12px;background:#F1F3F5;border:1px solid #E7E1D8;border-radius:11px;')}
    >
      <span aria-hidden="true" style={css('width:6px;height:6px;border-radius:50%;background:#9A6400;flex:none;')} />
      <span style={css("font:500 11px 'IBM Plex Sans';color:#6E685E;line-height:1.3;")}>
        {view.categoryFilterNote}
      </span>
    </div>
  )
}

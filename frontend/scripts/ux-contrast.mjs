#!/usr/bin/env node
// WCAG 2.1 contrast audit over the design tokens (plan-29 §4/§5.4). No deps: it
// imports the palette from src/styles/tokens.js and computes contrast ratios for
// the colour pairs the UI actually paints, classifying each against AA:
//   * normal text  → 4.5:1
//   * large text   → 3.0:1   (>=18.66px bold / >=24px regular)
//   * UI/graphics  → 3.0:1
//
// Advisory by default (always exits 0 so it never blocks a build) and prints a
// table. Pass --strict to exit non-zero when a CRITICAL pair (body text on the
// app backgrounds) drops below AA — that is the only thing worth gating CI on
// initially; button/muted findings are surfaced for the findings doc to track.

import { color } from '../src/styles/tokens.js'

const strict = process.argv.includes('--strict')
const json = process.argv.includes('--json')

// sRGB relative luminance per WCAG.
function luminance(hex) {
  const m = hex.replace('#', '')
  const rgb = [0, 2, 4].map((i) => parseInt(m.slice(i, i + 2), 16) / 255)
  const lin = rgb.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
}

function ratio(fg, bg) {
  const a = luminance(fg), b = luminance(bg)
  const [hi, lo] = a > b ? [a, b] : [b, a]
  return (hi + 0.05) / (lo + 0.05)
}

// kind: 'normal' | 'large' | 'ui'; critical pairs gate --strict.
const PAIRS = [
  { name: 'primary text on app background', fg: color.text, bg: color.bg, kind: 'normal', critical: true },
  { name: 'primary text on surface', fg: color.text, bg: color.surface, kind: 'normal', critical: true },
  { name: 'strong text on surface', fg: color.textStrong, bg: color.surface, kind: 'normal', critical: true },
  { name: 'body text on surface', fg: color.textBody, bg: color.surface, kind: 'normal', critical: true },
  { name: 'body text on app background', fg: color.textBody, bg: color.bg, kind: 'normal', critical: true },
  { name: 'muted text on surface', fg: color.textMuted, bg: color.surface, kind: 'normal', critical: false },
  { name: 'muted text on app background', fg: color.textMuted, bg: color.bg, kind: 'normal', critical: false },
  { name: 'faint text on surface (captions)', fg: color.textFaint, bg: color.surface, kind: 'large', critical: false },
  { name: 'white on primary button', fg: '#FFFFFF', bg: color.primary, kind: 'normal', critical: false },
  { name: 'white on success button', fg: '#FFFFFF', bg: color.success, kind: 'normal', critical: false },
  { name: 'link (primaryDark) on app background', fg: color.primaryDark, bg: color.bg, kind: 'normal', critical: false },
]

const THRESH = { normal: 4.5, large: 3.0, ui: 3.0 }

const rows = PAIRS.map((p) => {
  const r = ratio(p.fg, p.bg)
  const need = THRESH[p.kind]
  return { ...p, ratio: Math.round(r * 100) / 100, need, pass: r >= need }
})

if (json) {
  console.log(JSON.stringify(rows, null, 2))
} else {
  console.log('[ux-contrast] WCAG 2.1 AA contrast over design tokens\n')
  for (const r of rows) {
    const flag = r.pass ? 'PASS' : (r.critical ? 'FAIL*' : 'warn')
    console.log(`  ${flag.padEnd(6)} ${String(r.ratio).padStart(5)}:1 (need ${r.need})  ${r.name}`)
  }
  console.log('\n  * FAIL on a critical pair fails --strict. "warn" = below AA but not gated (track in findings).')
}

const criticalFails = rows.filter((r) => !r.pass && r.critical)
if (criticalFails.length && strict) {
  console.error(`\n[ux-contrast] STRICT FAIL — ${criticalFails.length} critical pair(s) below AA.`)
  process.exit(1)
}
process.exit(0)

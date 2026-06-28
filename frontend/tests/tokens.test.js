// Design-token sanity (plan-29 §4): the token module is well-formed and the
// refactored shared atoms actually consume it (so a stray hardcoded hex in the
// logo/banner shows up as a test failure, not a silent drift).
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement as h } from 'react'
import tokens, { color, fontSize, space, radius } from '../src/styles/tokens.js'
import Logo from '../src/components/Logo.jsx'

describe('tokens module', () => {
  it('exposes the core scales', () => {
    expect(color.primary).toMatch(/^#[0-9A-Fa-f]{6}$/)
    expect(color.bg).toBe('#F8F9FA')
    expect(tokens.color).toBe(color)
    expect(fontSize.base).toBe(13)
    expect(space[4]).toBe(16)
    expect(radius.md).toBe(11)
  })
})

describe('shared atoms consume tokens', () => {
  it('Logo paints with the primary brand color', () => {
    const html = renderToStaticMarkup(h(Logo, {}))
    expect(html.toUpperCase()).toContain(color.primary.toUpperCase())
  })
})

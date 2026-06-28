// Tests for the in-app UX feedback helper (plan-29 §6): the mailto is well-formed,
// carries non-personal context, and honors the per-deployment email override.
import { afterEach, describe, expect, it } from 'vitest'
import { feedbackMailto, feedbackEmail, DEFAULT_FEEDBACK_EMAIL } from '../src/lib/feedback.js'

afterEach(() => { try { localStorage.removeItem('egi_feedback_email') } catch { /* ignore */ } })

describe('feedbackMailto', () => {
  it('builds a mailto with subject and encoded context', () => {
    const url = feedbackMailto({ screen: 'shelters', lang: 'es', version: '1.2.3' })
    expect(url.startsWith(`mailto:${DEFAULT_FEEDBACK_EMAIL}?`)).toBe(true)
    expect(url).toContain('subject=')
    const body = decodeURIComponent(url.split('body=')[1])
    expect(body).toContain('shelters')
    expect(body).toContain('es')
    expect(body).toContain('1.2.3')
  })

  it('does not leak person data — only screen/lang/version/device', () => {
    const url = feedbackMailto({ screen: 'home', lang: 'en' })
    const body = decodeURIComponent(url.split('body=')[1])
    // device line is the UA; nothing here should reference cédula/name fields.
    expect(body.toLowerCase()).not.toContain('cedula')
  })
})

describe('feedbackEmail override', () => {
  it('falls back to the default', () => {
    expect(feedbackEmail()).toBe(DEFAULT_FEEDBACK_EMAIL)
  })
  it('honors localStorage override', () => {
    localStorage.setItem('egi_feedback_email', 'ops@example.org')
    expect(feedbackEmail()).toBe('ops@example.org')
  })
})

// In-app UX feedback intake (plan-29 §6). Offline-friendly and privacy-safe:
// it builds a pre-filled `mailto:` the device mail app opens — nothing is sent
// automatically, no analytics or tracking are added, and only non-personal
// context (current screen, language, app build, user-agent) is included. The
// destination can be overridden per-deployment via localStorage
// 'egi_feedback_email'. Mirrors docs/ux-audit/USER_FEEDBACK_TEMPLATE.md.

export const DEFAULT_FEEDBACK_EMAIL = 'soporte@egi.app'

export function feedbackEmail() {
  try {
    return localStorage.getItem('egi_feedback_email') || DEFAULT_FEEDBACK_EMAIL
  } catch { return DEFAULT_FEEDBACK_EMAIL }
}

// Non-personal device/context fields auto-attached to a report.
export function feedbackContext({ screen, lang } = {}) {
  const ua = (typeof navigator !== 'undefined' && navigator.userAgent) || 'unknown'
  return { screen: screen || 'unknown', lang: lang || 'unknown', userAgent: ua }
}

// Build the mailto: URL. `labels` carries the localized field names so the body
// reads in the user's language; all values are URL-encoded.
export function feedbackMailto({ screen, lang, version, labels } = {}) {
  const ctx = feedbackContext({ screen, lang })
  const L = labels || {}
  const subject = L.subject || 'EGI — problem report'
  const body = [
    `${L.screen || 'Screen'}: ${ctx.screen}`,
    `${L.language || 'Language'}: ${ctx.lang}`,
    `${L.version || 'Version'}: ${version || 'dev'}`,
    `${L.device || 'Device'}: ${ctx.userAgent}`,
    '',
    L.describe || 'Describe what happened:',
    '',
  ].join('\n')
  return `mailto:${feedbackEmail()}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

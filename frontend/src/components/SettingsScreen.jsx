import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { LangSelect } from './Sidebar.jsx'
import { BellIcon } from './Icons.jsx'
import NotificationSettings, { Toggle } from './NotificationSettings.jsx'
import { feedbackMailto } from '../lib/feedback.js'

// Settings / preferences (plan-24 Phase 2). Three grouped sections:
//   1. Categories I follow — per-category display / notify / relay toggles.
//   2. Notifications — near-me radius, quiet hours, batch digest.
//   3. Language & accessibility — existing device-level controls.
// Purely presentational: reads view.settingsCategories / view.settings and
// writes through actions.setCategoryPref / actions.setSetting.

// One column header above the three toggle switches.
function DimHeader({ label }) {
  return (
    <span style={css("width:42px;flex:none;text-align:center;font:600 8.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.03em;text-transform:uppercase;")}>
      {label}
    </span>
  )
}

function CategoryRow({ cat, actions, t }) {
  return (
    <div style={css('display:flex;align-items:center;gap:10px;padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:14px;')}>
      <div style={css('flex:1;min-width:0;')}>
        <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;display:flex;align-items:center;gap:6px;")}>
          {cat.label}
          {cat.critical && (
            <span style={css("font:600 8px 'IBM Plex Mono';color:#9A6400;background:#FBF4E6;padding:2px 5px;border-radius:5px;letter-spacing:.03em;")}>
              {t('settings.criticalBadge')}
            </span>
          )}
        </div>
        <div style={css("font:400 11px 'IBM Plex Sans';color:#8A837A;margin-top:2px;")}>{cat.desc}</div>
      </div>
      <Toggle on={cat.display} onClick={() => actions.setCategoryPref(cat.key, 'display', !cat.display)} label={cat.label + ' · ' + t('settings.dim.display')} />
      <Toggle on={cat.notify} onClick={() => actions.setCategoryPref(cat.key, 'notify', !cat.notify)} label={cat.label + ' · ' + t('settings.dim.notify')} />
      <Toggle on={cat.relay} onClick={() => actions.setCategoryPref(cat.key, 'relay', !cat.relay)} label={cat.label + ' · ' + t('settings.dim.relay')} />
    </div>
  )
}

function Section({ title, hint, children }) {
  return (
    <section style={css('margin-bottom:24px;')}>
      <h2 style={css("margin:0 0 2px;font:700 14px 'IBM Plex Sans';color:#1A1714;")}>{title}</h2>
      {hint && <p style={css("margin:0 0 12px;font:400 11.5px 'IBM Plex Sans';color:#8A837A;")}>{hint}</p>}
      {children}
    </section>
  )
}

export default function SettingsScreen({ view, actions }) {
  const v = view
  const { t, lang } = useI18n()
  const reportHref = feedbackMailto({
    screen: v.screen || 'settings',
    lang,
    labels: {
      subject: t('feedback.subject'),
      screen: t('feedback.screen'),
      language: t('feedback.language'),
      version: t('feedback.version'),
      device: t('feedback.device'),
      describe: t('feedback.describe'),
    },
  })
  return (
    <div style={css('padding:16px 18px 32px;')}>
      <h1 style={css("margin:0 0 2px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>
        {t('settings.title')}
      </h1>
      <p style={css("margin:0 0 20px;font:400 12.5px 'IBM Plex Sans';color:#8A837A;")}>
        {t('settings.subtitle')}
      </p>

      <Section title={t('settings.categories.title')} hint={t('settings.categories.hint')}>
        {/* Dimension legend */}
        <div style={css('display:flex;align-items:center;gap:10px;padding:0 13px 8px;')}>
          <span style={css('flex:1;')} />
          <DimHeader label={t('settings.dim.display')} />
          <DimHeader label={t('settings.dim.notify')} />
          <DimHeader label={t('settings.dim.relay')} />
        </div>
        <div style={css('display:flex;flex-direction:column;gap:8px;')}>
          {v.settingsCategories.map((cat) => (
            <CategoryRow key={cat.key} cat={cat} actions={actions} t={t} />
          ))}
        </div>
      </Section>

      <Section
        title={<span style={css('display:flex;align-items:center;gap:8px;')}><BellIcon size={16} /> {t('settings.notifications.title')}</span>}
        hint={t('settings.notifications.hint')}
      >
        <div style={css('padding:16px 15px;background:#fff;border:1px solid #EDE9E3;border-radius:14px;')}>
          <NotificationSettings view={v} actions={actions} />
        </div>
      </Section>

      <Section title={t('settings.access.title')}>
        <div style={css('display:flex;flex-direction:column;gap:8px;')}>
          {/* Language */}
          <div style={css('display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:14px;')}>
            <span style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{t('common.language')}</span>
            <LangSelect />
          </div>
          {/* Simple mode */}
          <div style={css('display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 13px;background:#fff;border:1px solid #EDE9E3;border-radius:14px;')}>
            <div style={css('flex:1;min-width:0;')}>
              <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;")}>{t('settings.simpleMode.title')}</div>
              <p style={css("margin:3px 0 0;font:400 11.5px 'IBM Plex Sans';color:#8A837A;")}>{t('settings.simpleMode.desc')}</p>
            </div>
            <Toggle on={v.simpleMode} onClick={actions.toggleSimpleMode} label={t('settings.simpleMode.title')} />
          </div>
        </div>
      </Section>

      {/* Report a problem (plan-29 §6): low-friction UX feedback. Opens the mail
          app with a pre-filled, non-personal context template — no tracking. */}
      <Section title={t('settings.feedback.title')} hint={t('settings.feedback.hint')}>
        <a href={reportHref} className="egi-tap" style={css("display:flex;align-items:center;justify-content:center;gap:8px;padding:13px;background:#fff;border:1px solid #E2DED8;border-radius:14px;text-decoration:none;font:600 13px 'IBM Plex Sans';color:#1A1714;")}>
          {t('settings.feedback.button')}
        </a>
      </Section>
    </div>
  )
}

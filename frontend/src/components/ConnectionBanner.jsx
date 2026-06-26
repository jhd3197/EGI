import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// The persistent online/offline strip shown above the content area.
export default function ConnectionBanner({ view }) {
  const v = view
  const { t } = useI18n()
  if (v.offline) {
    return (
      <div aria-live="polite" style={css('flex:none;display:flex;align-items:center;gap:10px;padding:8px 16px;background:#FCEDEC;border-top:1px solid #F6DAD7;border-bottom:1px solid #F6DAD7;z-index:25;')}>
        <span aria-hidden="true" style={css('width:8px;height:8px;border-radius:50%;background:#C2272D;flex:none;animation:egiPulse 1.6s ease-in-out infinite;')} />
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 12px 'IBM Plex Sans';color:#B7242A;line-height:1.2;")}>{t('banner.offlineTitle', { n: v.queue })}</div>
          <div style={css("font:500 10px 'IBM Plex Mono';color:#CC8E8A;line-height:1.3;")}>{t('banner.offlineSub', { n: v.queue })}</div>
        </div>
        <span style={css("font:600 11px 'IBM Plex Sans';color:#B7242A;flex:none;")}>{t('banner.offlineAction')}</span>
      </div>
    )
  }
  return (
    <div aria-live="polite" style={css('flex:none;display:flex;align-items:center;gap:10px;padding:8px 16px;background:#E9F4ED;border-top:1px solid #CCE6D6;border-bottom:1px solid #CCE6D6;z-index:25;')}>
      <span aria-hidden="true" style={css('width:8px;height:8px;border-radius:50%;background:#1B7A45;flex:none;')} />
      <div style={css('flex:1;min-width:0;')}>
        <div style={css("font:600 12px 'IBM Plex Sans';color:#15683A;line-height:1.2;")}>{t('banner.onlineTitle')}</div>
        <div style={css("font:500 10px 'IBM Plex Mono';color:#6FA585;line-height:1.3;")}>{t('banner.onlineSub')}</div>
      </div>
    </div>
  )
}

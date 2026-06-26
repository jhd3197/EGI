import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Privacy warning shown before the mesh is enabled for the first time. Mirrors
// the native Android consent dialog (same Spanish copy); consent persists so it
// only appears once. Enabling the mesh means nearby strangers can receive the
// public registry data, so this must be an explicit opt-in.
export default function MeshWarningModal({ view, actions }) {
  const { t } = useI18n()
  if (!view.meshWarnOpen) return null
  return (
    <div
      onClick={actions.declineMeshWarning}
      style={css('position:fixed;inset:0;z-index:60;background:rgba(26,23,20,.45);display:flex;align-items:center;justify-content:center;padding:22px;')}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={css('width:100%;max-width:380px;background:#fff;border-radius:18px;padding:22px;box-shadow:0 24px 48px -16px rgba(0,0,0,.4);')}
      >
        <h2 style={css("margin:0 0 10px;font:700 17px 'IBM Plex Sans';color:#1A1714;")}>{t('meshWarn.title')}</h2>
        <p style={css("margin:0 0 18px;font:400 13.5px 'IBM Plex Sans';color:#4A443D;line-height:1.5;")}>
          {t('meshWarn.body')}
        </p>
        <div style={css('display:flex;gap:9px;')}>
          <button
            onClick={actions.declineMeshWarning}
            className="egi-tap"
            style={css("flex:1;padding:12px;background:#fff;border:1px solid #E2DED8;border-radius:12px;color:#5A534C;font:600 13px 'IBM Plex Sans';cursor:pointer;")}
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={actions.acceptMeshWarning}
            className="egi-tap"
            style={css("flex:1;padding:12px;background:#E5343B;border:none;border-radius:12px;color:#fff;font:600 13px 'IBM Plex Sans';cursor:pointer;")}
          >
            {t('common.continue')}
          </button>
        </div>
      </div>
    </div>
  )
}

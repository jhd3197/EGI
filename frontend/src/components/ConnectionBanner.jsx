import { css } from '../lib/css.js'

// The persistent online/offline strip shown above the content area.
export default function ConnectionBanner({ view }) {
  const v = view
  if (v.offline) {
    return (
      <div style={css('flex:none;display:flex;align-items:center;gap:10px;padding:8px 16px;background:#FCEDEC;border-top:1px solid #F6DAD7;border-bottom:1px solid #F6DAD7;z-index:25;')}>
        <span style={css('width:8px;height:8px;border-radius:50%;background:#C2272D;flex:none;animation:egiPulse 1.6s ease-in-out infinite;')} />
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 12px 'IBM Plex Sans';color:#B7242A;line-height:1.2;")}>Sin conexión — {v.queue} en cola</div>
          <div style={css("font:500 10px 'IBM Plex Mono';color:#CC8E8A;line-height:1.3;")}>Offline — {v.queue} reports queued to sync</div>
        </div>
        <span style={css("font:600 11px 'IBM Plex Sans';color:#B7242A;flex:none;")}>Se sincronizará</span>
      </div>
    )
  }
  return (
    <div style={css('flex:none;display:flex;align-items:center;gap:10px;padding:8px 16px;background:#E9F4ED;border-top:1px solid #CCE6D6;border-bottom:1px solid #CCE6D6;z-index:25;')}>
      <span style={css('width:8px;height:8px;border-radius:50%;background:#1B7A45;flex:none;')} />
      <div style={css('flex:1;min-width:0;')}>
        <div style={css("font:600 12px 'IBM Plex Sans';color:#15683A;line-height:1.2;")}>Sincronizado — hace un momento</div>
        <div style={css("font:500 10px 'IBM Plex Mono';color:#6FA585;line-height:1.3;")}>All reports synced</div>
      </div>
    </div>
  )
}

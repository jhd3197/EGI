import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'

// Presentational sector card (SAR operations). Shows the sector name, a status
// chip (colour per status), the assigned volunteer alias, and contextual action
// buttons wired to handlers passed via props. The parent decides which actions
// are available (only after the user has joined the operation).
export default function SectorCard({ sector, joined, onClaim, onRelease, onCheckin, onClear, onRecheck }) {
  const { t } = useI18n()
  const s = sector
  const claimed = s.status !== 'unassigned' && !!(s.assigned_to || s.assigned_volunteer_id)

  const Btn = ({ label, onClick, bg, fg, border }) => (
    <button onClick={onClick} className="egi-tap" style={{ ...css("padding:8px 12px;border-radius:10px;font:600 11.5px 'IBM Plex Sans';cursor:pointer;"), background: bg, color: fg, border: border || 'none' }}>{label}</button>
  )

  return (
    <div style={css('padding:13px;background:#fff;border:1px solid #EDE9E3;border-radius:14px;')}>
      <div style={css('display:flex;align-items:flex-start;gap:8px;')}>
        <div style={css('flex:1;min-width:0;')}>
          <div style={css("font:600 14px 'IBM Plex Sans';color:#1A1714;line-height:1.2;")}>{s.name}</div>
          {(s.assigned_to) && (
            <div style={css("font:400 11.5px 'IBM Plex Sans';color:#8A837A;margin-top:3px;")}>{t('operations.assignedTo', { alias: s.assigned_to })}</div>
          )}
          {s.notes && <div style={css("font:400 11.5px 'IBM Plex Sans';color:#A9A299;margin-top:3px;")}>{s.notes}</div>}
        </div>
        <span style={{ ...css("padding:3px 9px;border-radius:7px;font:600 10.5px 'IBM Plex Sans';flex:none;"), background: s.statusBg, color: s.statusColor }}>{s.statusLabel}</span>
      </div>

      {joined && (
        <div style={css('display:flex;gap:7px;margin-top:11px;flex-wrap:wrap;')}>
          {!claimed && <Btn label={t('operations.claim')} onClick={onClaim} bg="#1A1714" fg="#fff" />}
          {claimed && <Btn label={t('operations.release')} onClick={onRelease} bg="#fff" fg="#8A837A" border="1px solid #E6E2DC" />}
          {s.status !== 'in_progress' && s.status !== 'cleared' && (
            <Btn label={t('operations.searchingHere')} onClick={onCheckin} bg="#FBEEDA" fg="#9A6400" />
          )}
          {s.status !== 'cleared' && <Btn label={t('operations.markCleared')} onClick={onClear} bg="#E3F2E7" fg="#1B7A45" />}
          {s.status !== 'needs_recheck' && <Btn label={t('operations.needsRecheck')} onClick={onRecheck} bg="#FCEDEC" fg="#C2272D" />}
        </div>
      )}
    </div>
  )
}

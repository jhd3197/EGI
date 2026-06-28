import { useEffect, useState } from 'react'
import { css } from '../lib/css.js'
import { useI18n } from '../i18n/index.js'
import { TokenGate } from './ModerationScreen.jsx'

// Org & verified-location admin tooling (plan-25 Phase 4). Operator-gated like
// the moderation screen. Create orgs, verify them, create locations, and mint
// one-time invite tokens whose claim_url an admin can share as a link/QR.

function Field({ value, onChange, placeholder }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={css("flex:1;min-width:0;box-sizing:border-box;padding:10px 12px;border:1px solid #E2DED8;border-radius:10px;font:400 13px 'IBM Plex Sans';color:#1A1714;background:#fff;outline:none;")}
    />
  )
}

// A highlighted box showing a generated one-time invite token + claim_url so the
// admin can copy it (or turn the URL into a QR). Tokens are shown once.
function InviteResult({ invite }) {
  const { t } = useI18n()
  if (!invite) return null
  return (
    <div style={css('margin-top:10px;padding:12px 13px;background:#FBFAF8;border:1px dashed #C9C2B8;border-radius:11px;')}>
      <div style={css("font:600 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;margin-bottom:4px;")}>{t('orgAdmin.inviteToken')}</div>
      <div style={css("font:600 12.5px 'IBM Plex Mono';color:#1A1714;word-break:break-all;margin-bottom:9px;")}>{invite.token}</div>
      {invite.claim_url && (
        <>
          <div style={css("font:600 9.5px 'IBM Plex Mono';color:#A9A299;letter-spacing:.04em;margin-bottom:4px;")}>{t('orgAdmin.claimUrl')}</div>
          <div style={css("font:500 11.5px 'IBM Plex Mono';color:#1F5E96;word-break:break-all;margin-bottom:9px;")}>{invite.claim_url}</div>
        </>
      )}
      <p style={css("margin:0;font:400 11px 'IBM Plex Sans';color:#8A837A;line-height:1.4;")}>{t('orgAdmin.qrHint')}</p>
    </div>
  )
}

function AdminBody({ actions }) {
  const { t } = useI18n()
  const [orgs, setOrgs] = useState([])
  const [locations, setLocations] = useState([])
  const [orgName, setOrgName] = useState('')
  const [orgKind, setOrgKind] = useState('')
  const [locName, setLocName] = useState('')
  const [locKind, setLocKind] = useState('')
  const [locOrgId, setLocOrgId] = useState('')
  const [invite, setInvite] = useState(null)

  const refresh = async () => {
    setOrgs(await actions.listOrgs())
    setLocations(await actions.listLocations())
  }
  useEffect(() => { refresh() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const doCreateOrg = async () => {
    if (!orgName.trim()) return
    await actions.createOrg({ name: orgName, kind: orgKind })
    setOrgName(''); setOrgKind(''); refresh()
  }
  const doVerify = async (id) => { await actions.verifyOrg(id, true); refresh() }
  const doOrgInvite = async (id) => {
    const res = await actions.createOrgInvite(id, {})
    if (res) setInvite(res)
  }
  const doCreateLocation = async () => {
    if (!locName.trim()) return
    await actions.createLocation({ name: locName, kind: locKind, orgId: locOrgId.trim() || null })
    setLocName(''); setLocKind(''); setLocOrgId(''); refresh()
  }
  const doLocInvite = async (id) => {
    const res = await actions.createLocationInvite(id, {})
    if (res) setInvite(res)
  }

  const sectionHead = css("margin:22px 0 10px;font:600 12px 'IBM Plex Mono';color:#6E685E;letter-spacing:.04em;text-transform:uppercase;")
  const card = css('background:#fff;border:1px solid #EDE9E3;border-radius:13px;padding:12px 13px;margin-bottom:9px;')
  const primaryBtn = css("flex:none;padding:10px 15px;background:#1A1714;border:none;border-radius:10px;color:#fff;font:600 12px 'IBM Plex Sans';cursor:pointer;")
  const smallBtn = css("flex:none;padding:7px 12px;background:#fff;border:1px solid #E2DED8;border-radius:9px;color:#5A534C;font:600 11px 'IBM Plex Sans';cursor:pointer;")

  return (
    <div>
      <InviteResult invite={invite} />

      <h2 style={sectionHead}>{t('orgAdmin.orgsSection')}</h2>
      <div style={css('display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;')}>
        <Field value={orgName} onChange={setOrgName} placeholder={t('orgAdmin.orgName')} />
        <Field value={orgKind} onChange={setOrgKind} placeholder={t('orgAdmin.orgKind')} />
        <button onClick={doCreateOrg} className="egi-tap" style={primaryBtn}>{t('orgAdmin.createOrg')}</button>
      </div>
      {orgs.length === 0 ? (
        <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('orgAdmin.empty')}</p>
      ) : orgs.map((o) => (
        <div key={o.id} style={card}>
          <div style={css('display:flex;align-items:center;gap:9px;')}>
            <div style={css('flex:1;min-width:0;')}>
              <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{o.name}</div>
              <div style={css("font:400 10px 'IBM Plex Mono';color:#A9A299;margin-top:2px;")}>{[o.kind, o.id].filter(Boolean).join(' · ')}</div>
            </div>
            {o.verified
              ? <span style={{ ...css("padding:5px 10px;border-radius:8px;font:600 11px 'IBM Plex Sans';flex:none;"), background: '#E9F4ED', color: '#15683A' }}>{t('orgAdmin.verified')}</span>
              : <button onClick={() => doVerify(o.id)} className="egi-tap" style={smallBtn}>{t('orgAdmin.verify')}</button>}
          </div>
          <button onClick={() => doOrgInvite(o.id)} className="egi-tap" style={{ ...css("margin-top:9px;width:100%;padding:9px;background:#fff;border:1px dashed #C9C2B8;border-radius:10px;color:#5A534C;font:600 11.5px 'IBM Plex Sans';cursor:pointer;") }}>{t('orgAdmin.genOrgInvite')}</button>
        </div>
      ))}

      <h2 style={sectionHead}>{t('orgAdmin.locationsSection')}</h2>
      <div style={css('display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;')}>
        <Field value={locName} onChange={setLocName} placeholder={t('orgAdmin.locationName')} />
        <Field value={locKind} onChange={setLocKind} placeholder={t('orgAdmin.locationKind')} />
        <Field value={locOrgId} onChange={setLocOrgId} placeholder={t('orgAdmin.orgIdOptional')} />
        <button onClick={doCreateLocation} className="egi-tap" style={primaryBtn}>{t('orgAdmin.createLocation')}</button>
      </div>
      {locations.length === 0 ? (
        <p style={css("font:400 12.5px 'IBM Plex Sans';color:#A9A299;")}>{t('orgAdmin.empty')}</p>
      ) : locations.map((l) => (
        <div key={l.id} style={card}>
          <div style={css('flex:1;min-width:0;')}>
            <div style={css("font:600 13px 'IBM Plex Sans';color:#1A1714;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")}>{l.name}</div>
            <div style={css("font:400 10px 'IBM Plex Mono';color:#A9A299;margin-top:2px;")}>{[l.kind, l.id].filter(Boolean).join(' · ')}</div>
          </div>
          <button onClick={() => doLocInvite(l.id)} className="egi-tap" style={{ ...css("margin-top:9px;width:100%;padding:9px;background:#fff;border:1px dashed #C9C2B8;border-radius:10px;color:#5A534C;font:600 11.5px 'IBM Plex Sans';cursor:pointer;") }}>{t('orgAdmin.genLocationInvite')}</button>
        </div>
      ))}
    </div>
  )
}

export default function OrgAdminScreen({ actions }) {
  const { t } = useI18n()
  const [tokenSet, setTokenSet] = useState(() => actions.isOperatorTokenSet())
  const [tokenInvalid, setTokenInvalid] = useState(false)
  useEffect(() => {
    const unsub = actions.subscribeOperatorToken(({ set, invalid }) => {
      setTokenSet(set)
      setTokenInvalid(!!invalid)
    })
    return unsub
  }, [actions])

  return (
    <div style={css('padding:14px 18px 28px;')}>
      <div style={css('display:flex;align-items:center;gap:12px;margin-bottom:4px;')}>
        <button onClick={() => actions.setScreen('moderation')} className="egi-tap" style={css('width:34px;height:34px;border-radius:50%;border:1px solid #E6E2DC;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none;')}>
          <span style={css('width:9px;height:9px;border-left:2px solid #1A1714;border-bottom:2px solid #1A1714;transform:rotate(45deg);margin-left:3px;')} />
        </button>
        <h1 style={css("flex:1;margin:0;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;")}>{t('orgAdmin.title')}</h1>
      </div>
      <p style={css("margin:0 0 14px;font:400 13px 'IBM Plex Sans';color:#8A837A;line-height:1.45;")}>{t('orgAdmin.intro')}</p>
      {tokenSet ? <AdminBody actions={actions} /> : <TokenGate actions={actions} invalid={tokenInvalid} />}
    </div>
  )
}

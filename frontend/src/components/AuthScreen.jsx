import { css } from '../lib/css.js'
import Logo from './Logo.jsx'
import Wordmark from './Wordmark.jsx'

export default function AuthScreen({ actions }) {
  return (
    <div style={css("height:100vh;width:100%;display:flex;align-items:center;justify-content:center;padding:24px;background:#F4EFE7;font-family:'IBM Plex Sans',system-ui,sans-serif;")}>
      <div style={css('width:100%;max-width:372px;display:flex;flex-direction:column;align-items:center;text-align:center;')}>
        <div style={css('display:flex;align-items:center;gap:11px;margin-bottom:20px;')}>
          <Logo size={40} radius={12} bar={21} thick={5} />
          <Wordmark size={32} />
        </div>
        <div style={css("font:600 13px 'IBM Plex Sans';color:#E5343B;margin-bottom:8px;")}>EGI, encuentra a los tuyos.</div>
        <div style={css("font:500 10px 'IBM Plex Mono';color:#A39B90;letter-spacing:.16em;margin-bottom:18px;")}>EMERGENCIA · GENTE · INFORMACIÓN</div>
        <h1 style={css("margin:0 0 10px;font:700 22px 'IBM Plex Sans';color:#1A1714;letter-spacing:-.01em;line-height:1.3;text-wrap:balance;")}>Ayuda a localizar a personas tras un desastre</h1>
        <p style={css("margin:0 0 28px;font:400 13.5px 'IBM Plex Sans';color:#6A645C;line-height:1.55;max-width:320px;")}>Reporta a un familiar, registra a quien está a salvo y reúne a las familias. Funciona sin conexión.</p>

        <button onClick={() => actions.signIn('google')} className="egi-tap" style={css("width:100%;display:flex;align-items:center;justify-content:center;gap:10px;padding:14px;background:#fff;border:1px solid #DCD6CD;border-radius:12px;cursor:pointer;font:600 14px 'IBM Plex Sans';color:#1A1714;margin-bottom:9px;")}>
          <span style={css("width:20px;height:20px;border-radius:50%;border:1.5px solid #D2362F;display:flex;align-items:center;justify-content:center;font:700 11px 'IBM Plex Sans';color:#D2362F;flex:none;")}>G</span>
          Continuar con Google
        </button>
        <button onClick={() => actions.signIn('guest')} className="egi-tap" style={css('width:100%;display:flex;flex-direction:column;align-items:center;gap:3px;padding:12px;background:transparent;border:1px solid #E2DCD2;border-radius:12px;cursor:pointer;')}>
          <span style={css("font:600 14px 'IBM Plex Sans';color:#1A1714;")}>Entrar como invitado</span>
          <span style={css("font:400 10.5px 'IBM Plex Mono';color:#A39B90;")}>Se guarda en este dispositivo · sin cuenta</span>
        </button>

        <div style={css('margin-top:26px;display:flex;align-items:center;gap:7px;')}>
          <span style={css('width:6px;height:6px;border-radius:50%;background:#C2272D;display:inline-block;')} />
          <span style={css("font:400 10.5px 'IBM Plex Mono';color:#A39B90;")}>Diseñada para zonas con poca o ninguna señal</span>
        </div>
      </div>
    </div>
  )
}

#!/usr/bin/env python3
"""EGI PWA WebView smoke test — drives the embedded PWA on real devices via CDP.

For each connected (or selected) device it runs three user journeys against the
REAL DOM, with no human interaction, and collects artifacts:

  Journey A — Guest entry: tap "Enter as guest", pick the first disaster, reach home.
  Journey B — Alias entry: type a unique alias, enter, assert it persists (IndexedDB).
  Journey C — Create report: open the missing-person sheet, fill + submit, assert the
              record reached the native Room backend (GET /persons count grows).

Each journey runs in its own fresh app state (`pm clear`) so they are independent.
Artifacts per device land in mobile/android/test-results/<serial>/:
  - <journey>.png        screenshot after the journey
  - <journey>.json       the journey verdict
  - console.log          captured window console messages
  - result.json          combined pass/fail summary

Exit code is non-zero if any journey on any device fails — so CI can gate on it.

Usage:
    python pwa_smoke_test.py                 # all connected devices
    python pwa_smoke_test.py <serial> ...    # specific devices
Env:
    EGI_BASELINE_DIR / visual diff is handled by the Phase-5 wrapper, not here.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pwa_cdp import CDPSession  # noqa: E402
import pwa_visual  # noqa: E402
import device_dialogs  # noqa: E402

PKG = "com.egi.app"
ACTIVITY = PKG + "/.MainActivity"
HARNESS = os.path.join(HERE, "pwa-test-harness.js")
RESULTS = os.path.join(HERE, "..", "test-results")
BASELINE = os.path.join(HERE, "..", "screenshots", "baseline")
# Fraction of pixels allowed to differ from the baseline before it's a failure.
# Tolerant enough to absorb dynamic content (status-bar clock, relative
# timestamps, mount animations); a real layout/font/colour regression differs far
# more. Override with EGI_VISUAL_THRESHOLD.
VISUAL_THRESHOLD = float(os.environ.get("EGI_VISUAL_THRESHOLD", "0.08"))
# Visual regression is opt-in (set EGI_VISUAL=1) so functional runs aren't gated
# by missing baselines; it always runs in update-baselines / CI when enabled.
VISUAL_ENABLED = os.environ.get("EGI_VISUAL", "0") == "1"


def visual_check(serial, journey):
    """Compare the journey screenshot to its baseline. Returns a verdict dict."""
    if not VISUAL_ENABLED:
        return {"checked": False, "reason": "disabled"}
    base = os.path.join(BASELINE, serial, journey + ".png")
    cand = os.path.join(RESULTS, serial, journey + ".png")
    diff_out = os.path.join(RESULTS, serial, journey + ".diff.png")
    if not pwa_visual.available():
        return {"checked": False, "reason": "pillow/numpy unavailable"}
    if not os.path.exists(base):
        return {"checked": False, "reason": "no baseline (run update-baselines.sh)"}
    ratio, detail = pwa_visual.diff_ratio(base, cand, diff_out)
    if ratio is None:
        return {"checked": False, "reason": detail}
    return {"checked": True, "ratio": ratio, "threshold": VISUAL_THRESHOLD,
            "ok": ratio <= VISUAL_THRESHOLD, "detail": detail}


def adb(serial, *args, check=False):
    res = subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError("adb %s: %s" % (" ".join(args), res.stderr.strip()))
    return res.stdout


def connected_devices():
    out = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout
    devs = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devs.append(parts[0])
    return devs


def screenshot(serial, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    res = subprocess.run(["adb", "-s", serial, "exec-out", "screencap", "-p"], capture_output=True)
    with open(path, "wb") as f:
        f.write(res.stdout)


def relaunch_fresh(serial):
    """Clear app data and relaunch so the journey starts at the auth screen.

    pm clear wipes runtime grants, so re-grant every dangerous permission BEFORE
    launching — that way the system permission dialog never appears and journey
    screenshots stay clean (no native dialog over the WebView)."""
    adb(serial, "shell", "am", "force-stop", PKG)
    adb(serial, "shell", "pm", "clear", PKG)
    device_dialogs.grant_all(serial)
    adb(serial, "logcat", "-c")
    adb(serial, "shell", "am", "start", "-n", ACTIVITY)


# Resilient waits that resolve to *false* when the condition is not met, so the
# caller can fail loudly instead of treating a timeout as success.
WAIT_ROOT_JS = (
    "new Promise(function(res){var n=0;var i=setInterval(function(){"
    "n++;var r=document.getElementById('root');"
    "if(r&&r.children.length){clearInterval(i);res(true);}"
    "else if(n>80){clearInterval(i);res(false);}},250);})"
)
WAIT_AUTH_JS = (
    "new Promise(function(res){var n=0;var i=setInterval(function(){"
    "n++;var e=document.getElementById('egi-alias');"
    "if(e){clearInterval(i);res(true);}"
    "else if(n>80){clearInterval(i);res(false);}},250);})"
)


def _evaluate_with_retry(session, expression, attempts=3):
    """Evaluate JS, retrying when the execution context is destroyed (reload)."""
    last_err = None
    for _ in range(attempts):
        try:
            return session.evaluate(expression)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.0)
    raise last_err or RuntimeError("evaluate failed after %d attempts" % attempts)


def _wait_root(session):
    return _evaluate_with_retry(session, WAIT_ROOT_JS)


def _wait_auth_screen(session):
    return _evaluate_with_retry(session, WAIT_AUTH_JS)


DIAG_INSTALL_JS = """
(function(){
  if (window.__egiDiag) return;
  var diag = { errors: [], consoleErrors: [], consoleLogs: [], started: Date.now() };
  window.__egiDiag = diag;
  window.addEventListener('error', function(e){
    diag.errors.push({ msg: e.message, file: e.filename, line: e.lineno, col: e.colno });
  });
  var origError = console.error.bind(console);
  console.error = function(){
    diag.consoleErrors.push(Array.from(arguments).map(String).join(' '));
    return origError.apply(null, arguments);
  };
  var origLog = console.log.bind(console);
  console.log = function(){
    diag.consoleLogs.push(Array.from(arguments).map(String).join(' '));
    return origLog.apply(null, arguments);
  };
})();
"""


def _install_diag(session):
    """Inject early error/console capture so we can see why the PWA failed to mount."""
    try:
        session.evaluate(DIAG_INSTALL_JS, await_promise=False)
    except Exception:  # noqa: BLE001
        pass


def _snapshot_page(session):
    """Return a small diagnostic dict describing the current WebView state."""
    try:
        return session.evaluate(
            "(function(){"
            "  var r=document.getElementById('root');"
            "  var mainScript=document.querySelector('script[type=\"module\"]');"
            "  var scriptStatus=null;"
            "  if(mainScript&&mainScript.src){"
            "    try{"
            "      var x=new XMLHttpRequest();"
            "      x.open('GET',mainScript.src,false);"
            "      x.send();"
            "      scriptStatus=x.status;"
            "    }catch(e){scriptStatus='error: '+String(e.message||e);}"
            "  }"
            "  var diag=window.__egiDiag||{};"
            "  return {"
            "    url: location.href,"
            "    readyState: document.readyState,"
            "    rootChildren: r&&r.children?r.children.length:0,"
            "    hasAlias: !!document.getElementById('egi-alias'),"
            "    title: document.title,"
            "    scriptSrc: mainScript?mainScript.src:null,"
            "    scriptStatus: scriptStatus,"
            "    userAgent: navigator.userAgent,"
            "    reactDefined: typeof window.React!=='undefined',"
            "    reactDOMDefined: typeof window.ReactDOM!=='undefined',"
            "    createRootDefined: typeof window.createRoot!=='undefined',"
            "    errors: diag.errors||[],"
            "    consoleErrors: (diag.consoleErrors||[]).slice(-20),"
            "    consoleLogs: (diag.consoleLogs||[]).slice(-20),"
            "    html: document.documentElement.outerHTML.slice(0,600)"
            "  };"
            "})()",
            await_promise=False,
        ) or {}
    except Exception:  # noqa: BLE001
        return {}


def open_session(serial, settle=4.0):
    """Connect CDP, force a deterministic Spanish UI, inject the harness.

    The emulator can be slow to mount the React tree, so we wait for the auth
    screen specifically (not just #root) before declaring the session ready.
    """
    time.sleep(settle)
    # With perms pre-granted the app auto-starts the mesh and shows its consent
    # AlertDialog over the WebView; tap it (and any straggler) away before driving.
    device_dialogs.accept_dialogs(serial)
    s = CDPSession(serial)
    s.connect()
    _install_diag(s)

    if not _wait_root(s):
        snap = _snapshot_page(s)
        raise RuntimeError("#root never gained children: %s" % snap)
    if not _wait_auth_screen(s):
        snap = _snapshot_page(s)
        raise RuntimeError("auth screen (#egi-alias) did not appear: %s" % snap)

    # The harness matches Spanish button text; the PWA otherwise picks the device
    # locale. Pin egi_lang=es and reload so journeys are locale-independent.
    lang = None
    try:
        lang = s.evaluate("try{localStorage.getItem('egi_lang')}catch(e){null}", await_promise=False)
    except Exception:
        pass
    if lang != "es":
        s.evaluate("try{localStorage.setItem('egi_lang','es')}catch(e){}", await_promise=False)
        s.evaluate("location.reload()", await_promise=False)
        # Re-dismiss any dialog that may have re-appeared while the page reloaded.
        device_dialogs.accept_dialogs(serial)
        _install_diag(s)
        if not _wait_root(s):
            snap = _snapshot_page(s)
            raise RuntimeError("#root never gained children after Spanish reload: %s" % snap)
        if not _wait_auth_screen(s):
            snap = _snapshot_page(s)
            raise RuntimeError("auth screen did not appear after Spanish reload: %s" % snap)

    s.inject_file(HARNESS)
    return s


def dump_console(serial, session):
    try:
        logs = session.evaluate("window.__egiTest ? window.__egiTest.logs : []") or []
    except Exception:
        logs = []
    path = os.path.join(RESULTS, serial, "console.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in logs:
            f.write("[%s] %s\n" % (e.get("level"), e.get("msg")))
    return logs


def run_journey(serial, name, runner_js, screenshot_after=True):
    """Fresh-state run of one journey. Returns the verdict dict."""
    relaunch_fresh(serial)
    verdict = {"journey": name, "ok": False, "detail": "session-failed"}
    session = None
    try:
        session = open_session(serial)
        verdict = session.evaluate(runner_js, timeout=60) or verdict
    except Exception as e:  # noqa: BLE001
        verdict = {"journey": name, "ok": False, "detail": "harness error: %s" % e}
    finally:
        if session:
            dump_console(serial, session)
            if screenshot_after:
                screenshot(serial, os.path.join(RESULTS, serial, name + ".png"))
            session.close()
    if screenshot_after:
        verdict["visual"] = visual_check(serial, name)
    out = os.path.join(RESULTS, serial, name + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2)
    return verdict


def test_device(serial):
    print("=== Device %s ===" % serial)
    ts = str(int(time.time()))
    journeys = [
        ("guest", "window.__egiTest.runGuest()"),
        ("alias", "window.__egiTest.runAlias('egi-test-%s')" % ts),
        # Journey C needs to be on home: enter as guest + pick disaster, then report.
        ("report",
         "window.__egiTest.runGuest().then(function(g){"
         "if(!g.ok) return Object.assign(g,{journey:'report',detail:'setup(guest) failed'});"
         "return window.__egiTest.runReport('Test Persona %s');})" % ts),
    ]
    results = []
    for name, js in journeys:
        v = run_journey(serial, name, js)
        ok = bool(v.get("ok"))
        vis = v.get("visual") or {}
        vis_note = ""
        if vis.get("checked"):
            vis_ok = vis.get("ok")
            ok = ok and vis_ok
            vis_note = "  visual=%s (%.2f%%)" % ("OK" if vis_ok else "DIFF", vis.get("ratio", 0) * 100)
        print("  [%s] %s — %s%s" % ("PASS" if ok else "FAIL", name, v.get("detail"), vis_note))
        v["pass"] = ok
        results.append(v)
    passed = all(r.get("pass", r.get("ok")) for r in results)
    summary = {"serial": serial, "ok": passed, "journeys": results}
    with open(os.path.join(RESULTS, serial, "result.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def main(argv):
    serials = argv[1:] or connected_devices()
    if not serials:
        sys.stderr.write("No connected devices.\n")
        return 2
    all_ok = True
    summaries = []
    for serial in serials:
        s = test_device(serial)
        summaries.append(s)
        all_ok = all_ok and s["ok"]
    print("\n=== Summary ===")
    for s in summaries:
        print("  %s: %s" % (s["serial"], "PASS" if s["ok"] else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

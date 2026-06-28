#!/usr/bin/env python3
"""EGI two-device mesh end-to-end test (plan-19 Phase 4).

Creates a missing-person report on phone A through the real PWA UI, turns on the
BLE mesh on both phones, and verifies the record propagates to phone B's local
store within a timeout — measuring the create→receive latency. Combines the
Phase-3 CDP harness with the BLE mesh.

Source of truth for pass/fail is phone B's native backend (GET /persons reads
Room), so the test confirms the record actually crossed the mesh into B's DB —
not merely that some UI updated. Screenshots of both phones are captured.

Preconditions:
  - At least two connected devices.
  - Bluetooth ON on both (the script checks and warns; enable with
    `adb -s <serial> shell svc bluetooth enable`).

Exit codes: 0 pass, 1 propagation failed within timeout, 2 skipped (need 2
devices / mesh unavailable on a device).

Usage:
    python mesh-pwa-e2e-test.py [A_serial B_serial]
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pwa_smoke_test import (  # noqa: E402
    RESULTS, adb, connected_devices, open_session, relaunch_fresh, screenshot,
)

# BLE discovery on real phones is subject to Android's "scanning too frequently"
# throttle (5 scans / 30 s), so allow a generous window for the duty cycle to
# advertise the new record and a peer to discover + pull it.
TIMEOUT_S = 150
ENABLE_MESH_JS = (
    "(function(){try{"
    "if(!window.EgiNative||!window.EgiNative.isAvailable())return {available:false};"
    "if(window.EgiNative.setMeshConsent)window.EgiNative.setMeshConsent(true);"
    "window.EgiNative.startMesh();"
    "return {available:true,deviceId:window.EgiNative.getDeviceId()};"
    "}catch(e){return {available:false,error:String(e)};}})()"
)


def bt_on(serial):
    return adb(serial, "shell", "settings", "get", "global", "bluetooth_on").strip() == "1"


BLE_PERMS = [
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.BLUETOOTH_ADVERTISE",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.ACCESS_FINE_LOCATION",
]


def grant_ble(serial):
    # pm clear (in relaunch_fresh) wipes runtime grants, so re-grant the BLE perms
    # the mesh needs. Granting while the app runs takes effect for the later
    # JS-driven startMesh; failures (e.g. perm absent on older API) are ignored.
    for perm in BLE_PERMS:
        adb(serial, "shell", "pm", "grant", "com.egi.app", perm)


def setup_home(serial):
    """Fresh launch → grant BLE perms → Spanish → enter as guest → first disaster → home."""
    relaunch_fresh(serial)
    grant_ble(serial)
    s = open_session(serial)
    g = s.evaluate("window.__egiTest.runGuest()", timeout=60) or {}
    return s, bool(g.get("ok"))


def persons(session):
    return session.evaluate("window.__egiTest.persons()", timeout=20) or []


def main(argv):
    serials = argv[1:] or connected_devices()
    if len(serials) < 2:
        print("SKIP: need two connected devices, found %d" % len(serials))
        return 2
    a, b = serials[0], serials[1]
    print("A=%s  B=%s" % (a, b))
    for s in (a, b):
        if not bt_on(s):
            print("WARN: Bluetooth OFF on %s — trying to enable..." % s)
            adb(s, "shell", "svc", "bluetooth", "enable")
            time.sleep(3)
        if not bt_on(s):
            print("SKIP: Bluetooth could not be enabled on %s" % s)
            return 2

    sA, okA = setup_home(a)
    sB, okB = setup_home(b)
    if not (okA and okB):
        print("SKIP: could not reach home on both (A=%s B=%s)" % (okA, okB))
        return 2

    mA = sA.evaluate(ENABLE_MESH_JS, await_promise=False) or {}
    mB = sB.evaluate(ENABLE_MESH_JS, await_promise=False) or {}
    print("mesh A=%s  B=%s" % (mA, mB))
    if not (mA.get("available") and mB.get("available")):
        print("SKIP: mesh unavailable on a device")
        return 2
    # Let advertising/scanning warm up before publishing the record.
    time.sleep(5)

    ts = str(int(time.time()))
    name = "Mesh Persona %s" % ts
    rep = sA.evaluate("window.__egiTest.runReport('%s')" % name, timeout=60) or {}
    print("A create report:", rep.get("ok"), rep.get("detail"))
    if not rep.get("ok"):
        print("FAIL: could not create the report on A")
        _finish(a, b, sA, sB, {"ok": False, "stage": "create", "detail": rep})
        return 1

    t0 = time.time()
    latency = None
    while time.time() - t0 < TIMEOUT_S:
        sA.evaluate("window.EgiMesh && window.EgiMesh.forceSync()", await_promise=False)
        sB.evaluate("window.EgiMesh && window.EgiMesh.forceSync()", await_promise=False)
        try:
            pB = persons(sB)
        except Exception:
            pB = []
        if any((p.get("name") or "").startswith(name) for p in pB):
            latency = round(time.time() - t0, 1)
            break
        time.sleep(3)

    ok = latency is not None
    print(("PASS: propagated to B in %ss" % latency) if ok else "FAIL: not on B within %ds" % TIMEOUT_S)
    # Bring B's UI to the people list so the screenshot shows the received record.
    try:
        sB.evaluate("window.__egiTest.clickByText('Buscar','*')", await_promise=True)
        time.sleep(1.5)
    except Exception:
        pass
    _finish(a, b, sA, sB, {
        "ok": ok, "record": name, "latency_s": latency, "timeout_s": TIMEOUT_S,
        "deviceA": a, "deviceB": b, "meshA": mA, "meshB": mB,
    })
    return 0 if ok else 1


def _finish(a, b, sA, sB, result):
    outdir = os.path.join(RESULTS, "mesh")
    os.makedirs(outdir, exist_ok=True)
    screenshot(a, os.path.join(outdir, "A-%s-sender.png" % a))
    screenshot(b, os.path.join(outdir, "B-%s-receiver.png" % b))
    with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    for s in (sA, sB):
        try:
            s.close()
        except Exception:
            pass
    print("artifacts ->", outdir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

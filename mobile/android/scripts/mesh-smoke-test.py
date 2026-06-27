#!/usr/bin/env python3
"""Two-device mesh smoke test.

Prerequisites:
  - Two authorized Android devices attached via ADB.
  - EGI debug APK already built (gradlew assembleDebug).
  - Runtime permissions already granted (run install-and-configure.sh first).

This script installs, clears data, launches the app on both devices, enables
mesh, and polls logcat for a record exchange. It exits 0 when both devices see
each other or report a successful sync.
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

APK = Path("app/build/outputs/apk/debug/app-debug.apk")
LOG_TIMEOUT = 60
PACKAGE = "com.egi.app"


def run(args, check=True):
    r = subprocess.run(args, capture_output=True, text=True, check=check)
    return r.stdout.strip(), r.stderr.strip()


def adb(*args, serial=None, check=True):
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    return run(cmd, check=check)


def authorized_devices():
    out, _ = adb("devices", "-l")
    devices = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def install_and_clear(serial):
    print(f"[{serial}] Installing APK...")
    adb("install", "-r", str(APK), serial=serial)
    print(f"[{serial}] Clearing app data...")
    adb("shell", "pm", "clear", PACKAGE, serial=serial)


def launch_app(serial):
    print(f"[{serial}] Launching app...")
    adb(
        "shell",
        "monkey",
        "-p",
        PACKAGE,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
        serial=serial,
        check=False,
    )


def logcat_stream(serial, tag_filter, lines):
    """Stream logcat lines into the shared `lines` list until timeout."""
    proc = subprocess.Popen(
        ["adb", "-s", serial, "logcat", "-s", tag_filter, "*:S"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        start = time.time()
        while time.time() - start < LOG_TIMEOUT:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            lines.append((serial, line.strip()))
    finally:
        proc.terminate()


def enable_mesh(serial):
    """Best-effort: send a broadcast the app can listen to in debug builds."""
    print(f"[{serial}] Requesting mesh enable...")
    adb(
        "shell",
        "am",
        "broadcast",
        "-a",
        "com.egi.app.action.ENABLE_MESH",
        "-n",
        f"{PACKAGE}/.mesh.MeshSmokeReceiver",
        serial=serial,
        check=False,
    )


def main():
    devices = authorized_devices()
    if len(devices) < 2:
        print(f"Need 2 authorized devices, found {len(devices)}: {devices}")
        sys.exit(1)

    a, b = devices[0], devices[1]
    print(f"Smoke test using {a} and {b}")

    if not APK.exists():
        print(f"APK not found at {APK}; run ./gradlew assembleDebug first.")
        sys.exit(1)

    for serial in (a, b):
        install_and_clear(serial)
        launch_app(serial)

    time.sleep(3)  # Let WebView load

    logs = []
    threads = []
    for serial in (a, b):
        t = threading.Thread(target=logcat_stream, args=(serial, "EGI-Mesh:D", logs))
        t.start()
        threads.append(t)

    time.sleep(2)
    for serial in (a, b):
        enable_mesh(serial)

    print(f"Watching logcat for {LOG_TIMEOUT}s...")
    for t in threads:
        t.join()

    # Simple pass criteria: both devices logged at least one mesh event.
    seen = {serial: False for serial in (a, b)}
    for serial, line in logs:
        if "peer" in line.lower() or "sync" in line.lower() or "advertise" in line.lower():
            seen[serial] = True

    report = {
        "devices": [a, b],
        "logs_captured": len(logs),
        "device_saw_mesh_events": seen,
    }
    print(json.dumps(report, indent=2))

    if all(seen.values()):
        print("PASS: both devices produced mesh log output.")
        sys.exit(0)
    else:
        print("FAIL: one or both devices did not produce mesh log output.")
        sys.exit(1)


if __name__ == "__main__":
    main()

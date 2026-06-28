#!/usr/bin/env python3
"""Hands-free Android dialog handling for EGI device tests.

After an install or `pm clear`, Android pops system runtime-permission dialogs
(Bluetooth / location / notifications), and the app shows its own mesh-consent
dialog on first mesh start. These render OUTSIDE the WebView, so CDP can't touch
them and they otherwise need manual taps on each device. This module clears them
automatically with two complementary techniques:

  grant_all(serial)      pm-grant every dangerous runtime permission BEFORE launch
                         so the system dialog never appears (deterministic, no taps,
                         locale-independent).
  accept_dialogs(serial) uiautomator-based fallback that taps Allow / Permitir /
                         "While using the app" / Continuar / OK for anything still
                         showing (e.g. the app's consent AlertDialog). UI-tree based,
                         not screenshot matching, so it's robust to theme/resolution.

CLI:
    python device_dialogs.py grant <serial>
    python device_dialogs.py accept <serial>
    python device_dialogs.py clear <serial>     # grant + accept
"""
import re
import subprocess
import sys
import time

PKG = "com.egi.app"

# Dangerous (runtime) permissions the app declares. Normal/install-time ones
# (INTERNET, BLUETOOTH, FOREGROUND_SERVICE, *_NETWORK_STATE) are auto-granted and
# rejected by `pm grant`, so they're omitted here.
DANGEROUS_PERMS = [
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.BLUETOOTH_ADVERTISE",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.NEARBY_WIFI_DEVICES",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.RECEIVE_SMS",
]

# Lowercased button labels that mean "accept", across the locales EGI ships.
ACCEPT_WORDS = [
    "while using the app", "only this time", "allow",
    "mientras usas la app", "solo esta vez", "permitir",
    "continuar", "continue", "aceptar", "entendido", "ok",
]
# Never tap these even if they contain an accept-ish word.
DENY_WORDS = ["don't allow", "no permitir", "deny", "cancelar", "cancel"]


def adb(serial, *args, check=False):
    res = subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError("adb %s: %s" % (" ".join(args), res.stderr.strip()))
    return res.stdout


def grant_all(serial):
    """Grant every dangerous runtime permission. Missing ones (older API) are ignored."""
    granted = 0
    for perm in DANGEROUS_PERMS:
        res = subprocess.run(
            ["adb", "-s", serial, "shell", "pm", "grant", PKG, perm],
            capture_output=True, text=True,
        )
        if res.returncode == 0:
            granted += 1
    return granted


def _dump_ui(serial):
    """Return the uiautomator XML hierarchy, or '' if the dump failed."""
    # Dump to a file then read it back — more reliable across devices than
    # /dev/stdout (some OEMs prepend a status line or fail on the stdout sink).
    remote = "/sdcard/egi_ui_dump.xml"
    res = subprocess.run(
        ["adb", "-s", serial, "shell", "uiautomator", "dump", remote],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or 'UI hierchary dumped to' not in res.stdout:
        # On some emulators uiautomator dumps to a default path; try reading it.
        remote = "/sdcard/window_dump.xml"
    return adb(serial, "shell", "cat", remote)


def _accept_targets(xml):
    """Yield (cx, cy, label) tap centers for clickable accept-BUTTONS in the dump.

    Only `clickable="true"` nodes qualify, so a dialog's message body — which may
    itself contain an accept word like "¿continuar?" — is never tapped; only the
    actual button is. Shorter labels are preferred (a real button is "Continuar",
    not a paragraph), guarding against a clickable container wrapping the message."""
    candidates = []
    for m in re.finditer(r"<node\b[^>]*?>", xml):
        node = m.group(0)
        if 'clickable="true"' not in node:
            continue
        text = (re.search(r'text="([^"]*)"', node) or [None, ""])[1].lower()
        desc = (re.search(r'content-desc="([^"]*)"', node) or [None, ""])[1].lower()
        label = (text + " " + desc).strip()
        if not label or len(label) > 40:
            continue
        if any(d in label for d in DENY_WORDS):
            continue
        if not any(w in label for w in ACCEPT_WORDS):
            continue
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
        if not b:
            continue
        x1, y1, x2, y2 = map(int, b.groups())
        candidates.append((len(label), (x1 + x2) // 2, (y1 + y2) // 2, label))
    candidates.sort()  # shortest (most button-like) label first
    return [(cx, cy, label) for _, cx, cy, label in candidates]


def accept_dialogs(serial, rounds=8, settle=1.0):
    """Tap accept-buttons until none remain (handles back-to-back dialogs).

    The emulator can take a while to render the mesh consent AlertDialog, so we
    poll for several seconds before giving up.
    """
    tapped = []
    for _ in range(rounds):
        xml = _dump_ui(serial)
        targets = list(_accept_targets(xml))
        if not targets:
            break
        cx, cy, label = targets[0]
        adb(serial, "shell", "input", "tap", str(cx), str(cy))
        tapped.append(label)
        time.sleep(settle)
    return tapped


def clear(serial):
    grant_all(serial)
    return accept_dialogs(serial)


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    cmd, serial = argv[1], argv[2]
    if cmd == "grant":
        print("granted", grant_all(serial), "permissions on", serial)
    elif cmd == "accept":
        print("tapped:", accept_dialogs(serial))
    elif cmd == "clear":
        n = grant_all(serial)
        print("granted", n, "perms; tapped:", accept_dialogs(serial))
    else:
        sys.stderr.write("unknown command %s\n" % cmd)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

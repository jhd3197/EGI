#!/usr/bin/env python3
"""List and inspect Android devices attached via ADB."""
import json
import re
import subprocess
import sys
from pathlib import Path


def run(args, check=True):
    result = subprocess.run(
        args, capture_output=True, text=True, check=check, encoding="utf-8", errors="replace"
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def adb(*args, serial=None, check=True):
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    return run(cmd, check=check)


def list_devices():
    out, _, _ = adb("devices", "-l")
    devices = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        serial = parts[0]
        state = "unknown"
        props = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                props[k] = v
            elif state == "unknown":
                state = p
        devices.append({"serial": serial, "state": state, **props})
    return devices


def device_info(serial):
    info = {}
    out, _, _ = adb("shell", "getprop", serial=serial)
    for line in out.splitlines():
        m = re.match(r"\[(.+?)\]: \[(.*?)\]", line)
        if m:
            info[m.group(1)] = m.group(2)
    return info


def is_egi_installed(serial):
    out, _, rc = adb("shell", "pm", "list", "packages", "com.egi.app", serial=serial, check=False)
    return rc == 0 and "com.egi.app" in out


def battery(serial):
    out, _, _ = adb("shell", "dumpsys", "battery", serial=serial)
    level = re.search(r"level:\s*(\d+)", out)
    status = re.search(r"status:\s*(\d+)", out)
    return {
        "level": int(level.group(1)) if level else None,
        "status": int(status.group(1)) if status else None,
    }


def main():
    devices = list_devices()
    if not devices:
        print("No ADB devices attached.")
        sys.exit(1)

    rows = []
    for d in devices:
        serial = d["serial"]
        state = d["state"]
        props = device_info(serial) if state == "device" else {}
        installed = is_egi_installed(serial) if state == "device" else False
        bat = battery(serial) if state == "device" else {}
        rows.append(
            {
                "serial": serial,
                "state": state,
                "model": props.get("ro.product.model", ""),
                "android": props.get("ro.build.version.release", ""),
                "api": props.get("ro.build.version.sdk", ""),
                "egi_installed": installed,
                "battery": bat.get("level"),
            }
        )

    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'Serial':<16} {'State':<14} {'Model':<20} {'Android':<8} {'API':<4} {'EGI':<6} {'Batt'}")
        for r in rows:
            print(
                f"{r['serial']:<16} {r['state']:<14} {r['model']:<20} "
                f"{r['android']:<8} {r['api']:<4} {('yes' if r['egi_installed'] else 'no'):<6} {r['battery']}%"
            )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Minimal Chrome DevTools Protocol (CDP) client for driving the EGI WebView.

The Android app enables WebView remote debugging in debug builds
(`WebView.setWebContentsDebuggingEnabled(true)`), which exposes a CDP endpoint on a
local-abstract socket `webview_devtools_remote_<pid>`. This module forwards that
socket to a localhost TCP port, finds the PWA page, and runs JavaScript in it via
`Runtime.evaluate` (returning values by value, awaiting promises).

Used by pwa-smoke-test.sh / mesh tests to inject the test harness and run journeys
without any human interaction. Requires `websocket-client` (already installed).

CLI:
    python pwa_cdp.py <serial> eval "<js expression>"
    python pwa_cdp.py <serial> evalfile <path-to-js>     # inject a script file
"""
import json
import subprocess
import sys
import time
import urllib.request

try:
    import websocket  # websocket-client
except ImportError:
    sys.stderr.write("ERROR: websocket-client not installed (pip install websocket-client)\n")
    raise

PKG = "com.egi.app"


def _adb(serial, *args, check=True):
    cmd = ["adb", "-s", serial, *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError("adb %s failed: %s" % (" ".join(args), res.stderr.strip()))
    return res.stdout.strip()


def _pid(serial):
    out = _adb(serial, "shell", "pidof", PKG, check=False)
    return out.split()[0] if out else None


def _devtools_socket(serial):
    """Return the webview_devtools_remote_<...> abstract socket name for our app."""
    out = _adb(serial, "shell", "cat", "/proc/net/unix", check=False)
    names = []
    for line in out.splitlines():
        # Last column is the path; abstract sockets start with '@'.
        parts = line.split()
        if parts and "webview_devtools_remote" in parts[-1]:
            names.append(parts[-1].lstrip("@"))
    if not names:
        return None
    pid = _pid(serial)
    if pid:
        for n in names:
            if n.endswith("_" + pid):
                return n
    return names[0]


class CDPSession:
    def __init__(self, serial, timeout=20):
        self.serial = serial
        self.timeout = timeout
        self.local_port = None
        self.ws = None
        self._id = 0

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    def connect(self):
        socket_name = None
        # The devtools socket appears shortly after the WebView is created.
        for _ in range(int(self.timeout / 0.5)):
            socket_name = _devtools_socket(self.serial)
            if socket_name:
                break
            time.sleep(0.5)
        if not socket_name:
            raise RuntimeError("no webview_devtools_remote socket for %s (is a debug build running?)" % PKG)

        # Forward to an OS-assigned local port.
        out = _adb(self.serial, "forward", "tcp:0", "localabstract:" + socket_name)
        self.local_port = int(out.strip())

        ws_url = self._page_ws_url()
        # Modern Chromium rejects CDP WebSocket handshakes that carry a localhost
        # Origin header (403 Forbidden) unless launched with --remote-allow-origins.
        # Omitting the Origin entirely is accepted, so suppress it.
        self.ws = websocket.create_connection(
            ws_url, timeout=self.timeout, max_size=None, suppress_origin=True,
        )
        return self

    def _page_ws_url(self):
        url = "http://127.0.0.1:%d/json" % self.local_port
        last = None
        for _ in range(20):
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    pages = json.loads(r.read().decode("utf-8"))
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(0.5)
                continue
            # Prefer the PWA page served from the asset-loader origin.
            for p in pages:
                if p.get("type") == "page" and "appassets.androidplatform.net" in p.get("url", ""):
                    if p.get("webSocketDebuggerUrl"):
                        return p["webSocketDebuggerUrl"]
            for p in pages:
                if p.get("webSocketDebuggerUrl"):
                    return p["webSocketDebuggerUrl"]
            time.sleep(0.5)
        raise RuntimeError("no debuggable WebView page found (%s)" % last)

    def evaluate(self, expression, await_promise=True, timeout=30):
        """Run JS and return the value (returnByValue). Raises on JS exception."""
        self._id += 1
        msg_id = self._id
        self.ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
                "allowUnsafeEvalBlockedByCSP": True,
            },
        }))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.ws.settimeout(max(1, deadline - time.time()))
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") != msg_id:
                continue  # skip events / other replies
            if "error" in data:
                raise RuntimeError("CDP error: %s" % data["error"])
            result = data.get("result", {})
            if result.get("exceptionDetails"):
                exc = result["exceptionDetails"]
                txt = exc.get("exception", {}).get("description") or json.dumps(exc)
                raise RuntimeError("JS exception: %s" % txt)
            return result.get("result", {}).get("value")
        raise RuntimeError("CDP evaluate timed out")

    def inject_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        # Wrap so a trailing expression doesn't leak; harness is an IIFE already.
        return self.evaluate(src, await_promise=False)

    def close(self):
        try:
            if self.ws:
                self.ws.close()
        finally:
            if self.local_port:
                subprocess.run(["adb", "-s", self.serial, "forward", "--remove", "tcp:%d" % self.local_port],
                               capture_output=True, text=True)


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    serial, cmd = argv[1], argv[2]
    with CDPSession(serial) as s:
        if cmd == "eval":
            print(json.dumps(s.evaluate(argv[3])))
        elif cmd == "evalfile":
            s.inject_file(argv[3])
            print("injected", argv[3])
        else:
            sys.stderr.write("unknown command %s\n" % cmd)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

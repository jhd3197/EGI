"""Single source of truth for the EGI server version.

Surfaced by ``GET /health`` and the ``egi_build_info`` metric so operators can
tell which build is running.

The major.minor base lives in the repo-root ``VERSION`` file, shared with the
Android app (``mobile/android/app/build.gradle``) and the android-release
workflow, so the server and app never drift on the milestone line. The server
has no CI build number, so it reports ``<base>.0`` (e.g. ``0.1.0``). Bump the
milestone by editing ``VERSION``; if the file is missing (e.g. an odd packaging
layout), fall back to the last-known base so import never fails.
"""

from pathlib import Path

_FALLBACK_BASE = "0.1"


def _read_base() -> str:
    try:
        base = (Path(__file__).resolve().parent.parent / "VERSION").read_text().strip()
        return base or _FALLBACK_BASE
    except OSError:
        return _FALLBACK_BASE


__version__ = f"{_read_base()}.0"

"""Filesystem locations and server-import helpers shared by every command.

The CLI lives at the repo root but the FastAPI server is a set of top-level
modules under ``server/`` (it does ``import db``, ``import main`` directly).
``ensure_server_importable()`` puts ``server/`` on ``sys.path`` so commands can
``import db`` / ``import main`` the same way the server and its tests do.
"""

import os
import sys
from pathlib import Path

# egi_cli/paths.py -> egi_cli/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO_ROOT / "server"
FRONTEND_DIR = REPO_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


def ensure_server_importable() -> Path:
    """Put ``server/`` on ``sys.path`` (idempotent) and return its path.

    Mirrors how server/tests/conftest.py makes the server package importable.
    """
    server = str(SERVER_DIR)
    if server not in sys.path:
        sys.path.insert(0, server)

    # The server's db.py / main.py default DB_PATH and UPLOAD_DIR to paths
    # *relative to the CWD* (./data, ./uploads). The server is launched from
    # server/, but the CLI runs from the repo root (or anywhere), so without
    # this the CLI would touch a different DB than the running server. Pin them
    # to absolute paths under server/ unless the operator set them explicitly.
    # Load server/.env first so an operator's DB_PATH override is respected.
    _load_server_env()
    os.environ.setdefault("DB_PATH", str(SERVER_DIR / "data" / "egi.db"))
    os.environ.setdefault("UPLOAD_DIR", str(SERVER_DIR / "uploads"))
    return SERVER_DIR


def _load_server_env() -> None:
    """Best-effort load of server/.env so CLI commands see the same config as
    the server. Silent if python-dotenv or the file is missing."""
    env_file = SERVER_DIR / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file)
    except Exception:
        pass

"""``egi backend`` — start the FastAPI sync server (and serve the built PWA)."""

import subprocess
import sys

import click

from ..paths import FRONTEND_DIST, SERVER_DIR


@click.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind host.")
@click.option("--port", default=3000, show_default=True, type=int, help="Bind port.")
@click.option("--debug", is_flag=True, help="Enable uvicorn --reload for development.")
@click.option(
    "--build/--no-build",
    "build_frontend",
    default=False,
    help="Build the frontend into frontend/dist/ before starting.",
)
def backend(host, port, debug, build_frontend):
    """Start the FastAPI server. With it running the full app is at http://host:port."""
    if build_frontend:
        from .build import _run_build

        _run_build()

    if not FRONTEND_DIST.exists():
        click.secho(
            "Note: frontend/dist/ not found — API will run but the app UI won't be "
            "served. Run `egi build` (or `egi backend --build`) first.",
            fg="yellow",
        )

    # Run uvicorn from server/ so the server's relative defaults (DB_PATH=./data,
    # FRONTEND_DIR=../frontend/dist, UPLOAD_DIR=./uploads) resolve correctly.
    cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", host, "--port", str(port),
    ]
    if debug:
        cmd.append("--reload")

    click.secho(f"Starting EGI server on http://{host}:{port}", fg="green")
    raise SystemExit(subprocess.call(cmd, cwd=str(SERVER_DIR)))

"""``egi frontend`` — start the Vite dev server (proxies API to the Python server)."""

import shutil
import subprocess

import click

from ..paths import FRONTEND_DIR


def _npm() -> str:
    # On Windows npm is npm.cmd; shutil.which resolves whichever exists.
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


@click.command()
@click.option("--port", default=5173, show_default=True, type=int, help="Vite dev port.")
def frontend(port):
    """Start the Vite dev server on http://localhost:port (proxies /api to :3000)."""
    if not (FRONTEND_DIR / "package.json").exists():
        raise click.ClickException(f"No package.json in {FRONTEND_DIR}")
    if not (FRONTEND_DIR / "node_modules").exists():
        click.secho("node_modules/ missing — run `npm install` in frontend/ first.", fg="yellow")

    cmd = [_npm(), "run", "dev", "--", "--port", str(port)]
    click.secho(f"Starting Vite dev server on http://localhost:{port}", fg="green")
    raise SystemExit(subprocess.call(cmd, cwd=str(FRONTEND_DIR)))

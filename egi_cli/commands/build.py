"""``egi build`` — build the frontend into frontend/dist/ (served by FastAPI)."""

import shutil
import subprocess

import click

from ..paths import FRONTEND_DIR, FRONTEND_DIST


def _npm() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def _run_build() -> None:
    """Run `npm run build` in frontend/. Raises ClickException on failure."""
    if not (FRONTEND_DIR / "package.json").exists():
        raise click.ClickException(f"No package.json in {FRONTEND_DIR}")
    if not (FRONTEND_DIR / "node_modules").exists():
        click.secho("node_modules/ missing — running `npm install` first…", fg="yellow")
        if subprocess.call([_npm(), "install"], cwd=str(FRONTEND_DIR)) != 0:
            raise click.ClickException("npm install failed")

    click.secho("Building frontend…", fg="green")
    rc = subprocess.call([_npm(), "run", "build"], cwd=str(FRONTEND_DIR))
    if rc != 0:
        raise click.ClickException("Frontend build failed")
    click.secho(f"Built -> {FRONTEND_DIST}", fg="green")


@click.command()
def build():
    """Build the frontend production bundle into frontend/dist/."""
    _run_build()

"""Top-level ``egi`` Click group. Each command lives in egi_cli/commands/."""

import click

from . import __version__
from .commands.backend import backend
from .commands.backup import backup, restore
from .commands.build import build
from .commands.export_pfif import export_pfif
from .commands.federation import peer
from .commands.frontend import frontend
from .commands.generate_synthetic import generate_synthetic
from .commands.import_pfif import import_pfif
from .commands.ocr_review import ocr_review
from .commands.quality import quality_scan
from .commands.retention import anonymize, retention_review
from .commands.seed import seed
from .commands.unseed import unseed
from .commands.users import user


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="egi")
def cli():
    """EGI — developer/operator CLI for the disaster-reunification system.

    Run the server, build the PWA, and move/seed data. This is a dev/ops tool;
    it is kept out of the production PWA/APK.
    """


# Dev/run commands
cli.add_command(backend)
cli.add_command(frontend)
cli.add_command(build)
# Data operations
cli.add_command(seed)
cli.add_command(unseed)
cli.add_command(export_pfif)
cli.add_command(import_pfif)
cli.add_command(generate_synthetic)
cli.add_command(ocr_review)
cli.add_command(user)
cli.add_command(peer)
# Operations
cli.add_command(backup)
cli.add_command(restore)
cli.add_command(retention_review)
cli.add_command(anonymize)
cli.add_command(quality_scan)


if __name__ == "__main__":
    cli()

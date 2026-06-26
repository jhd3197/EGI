"""egi — developer/operator CLI for the EGI disaster-reunification system.

This package is a thin Click wrapper around the FastAPI server in ``server/``.
It is a development/operations tool and is deliberately kept out of the
production PWA/APK (plan §12). All data-operation commands import the server
modules lazily (after putting ``server/`` on ``sys.path``) so that ``egi --help``
stays fast and does not require the server's heavier dependencies.
"""

__version__ = "0.1.0"

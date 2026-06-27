"""Single source of truth for the EGI server version.

Surfaced by ``GET /health`` and the ``egi_build_info`` metric so operators can
tell which build is running. Bump this when cutting a release.
"""

__version__ = "0.1.0"

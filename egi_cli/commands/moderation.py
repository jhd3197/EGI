"""``egi moderation`` — moderation stats & flags for operators (plan-25 Phase 5).

Read-only operator visibility into the moderation queue and the flag backlog.
Thin Click wrappers over ``server/modules/moderation.py`` + ``moderators.py``.
"""

import click


def _mods():
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from modules import moderation, moderators  # noqa: E402

    return moderation, moderators


@click.group(name="moderation", context_settings={"help_option_names": ["-h", "--help"]})
def moderation():
    """Moderation queue statistics and flags."""


@moderation.command()
def stats():
    """Show moderation + flag + moderator-digest counts."""
    mod, mods = _mods()
    s = mod.stats()
    f = mod.flag_stats()
    d = mods.digest()
    click.secho("Records:", fg="cyan", bold=True)
    click.echo(f"  pending={s.get('pending', 0)}  approved={s.get('approved', 0)}  rejected={s.get('rejected', 0)}")
    click.secho("Flags:", fg="cyan", bold=True)
    click.echo(f"  open={f.get('open', 0)}  critical_open={f.get('critical_open', 0)}")
    if f.get("by_reason"):
        click.echo("  by reason: " + ", ".join(f"{k}={v}" for k, v in f["by_reason"].items()))
    click.secho("Moderators:", fg="cyan", bold=True)
    click.echo(f"  active={d.get('moderators', 0)}")


@moderation.command()
@click.option("--status", default="open", help="open | resolved | dismissed | all")
@click.option("--type", "record_type", default=None, help="Filter by record_type.")
def flags(status, record_type):
    """List moderation flags."""
    mod, _ = _mods()
    rows = mod.list_flags(status=status, record_type=record_type)["flags"]
    if not rows:
        click.echo("No flags.")
        return
    header = f"{'ID':<18} {'TYPE':<14} {'RECORD':<16} {'REASON':<14} {'SEV':<9} STATUS"
    click.echo(header)
    click.echo("-" * len(header))
    for r in rows:
        click.echo(
            f"{(r.get('id') or '')[:17]:<18} "
            f"{(r.get('record_type') or ''):<14} "
            f"{(r.get('record_id') or '')[:15]:<16} "
            f"{(r.get('flag_reason') or ''):<14} "
            f"{(r.get('severity') or ''):<9} "
            f"{r.get('status') or ''}"
        )

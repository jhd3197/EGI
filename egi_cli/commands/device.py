"""``egi device`` — device reputation & blocklist for operators (plan-25 Phase 5).

Ban a malicious mesh device by its fingerprint (``persons.origin_device``): its
records are hidden, future syncs from it are rejected, and the id joins the
blocklist bundle that gateways relay to offline peers. Thin Click wrappers over
``server/modules/device_reputation.py``; the server is imported lazily after
``ensure_server_importable()`` so the CLI touches the same DB as ``egi backend``.
"""

import click


def _device_reputation():
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from modules import device_reputation  # noqa: E402

    return device_reputation


@click.group(name="device", context_settings={"help_option_names": ["-h", "--help"]})
def device():
    """Inspect and ban/unban mesh devices."""


@device.command()
@click.argument("device_id")
@click.option("--reason", default=None, help="Why the device is being banned (audited).")
def ban(device_id, reason):
    """Ban a device fingerprint."""
    rep = _device_reputation().set_banned(device_id, True, reason=reason)
    click.secho(f"Banned {device_id} (score={rep.get('reputation_score')}).", fg="red")


@device.command()
@click.argument("device_id")
def unban(device_id):
    """Lift a device ban."""
    _device_reputation().set_banned(device_id, False)
    click.secho(f"Unbanned {device_id}.", fg="green")


@device.command(name="list")
@click.option("--banned", is_flag=True, help="Show only banned devices.")
def list_cmd(banned):
    """List device reputation rows."""
    rows = _device_reputation().list_devices(banned=True if banned else None)
    if not rows:
        click.echo("No devices found.")
        return
    header = f"{'DEVICE':<28} {'TIER':<7} {'SCORE':<6} {'REPORTS':<8} {'FLAGS':<6} {'BANNED':<6} LAST_SEEN"
    click.echo(header)
    click.echo("-" * len(header))
    for r in rows:
        click.echo(
            f"{(r.get('device_id') or '')[:27]:<28} "
            f"{(r.get('trust_tier') or ''):<7} "
            f"{str(r.get('reputation_score') or 0):<6} "
            f"{str(r.get('report_count') or 0):<8} "
            f"{str(r.get('flag_count') or 0):<6} "
            f"{('yes' if r.get('banned') else 'no'):<6} "
            f"{r.get('last_seen') or '-'}"
        )

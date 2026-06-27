"""``egi peer`` — manage trusted federation peers (plan-12 §4).

Thin Click wrappers over ``server/modules/federation.py``. Every callback puts
the server on ``sys.path`` via ``ensure_server_importable()`` before importing
it, so the CLI always touches the same DB as a running ``egi backend``.
"""

import click


def _federation():
    """Import the server federation module lazily (after pinning DB_PATH)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from modules import federation  # noqa: E402

    return federation


@click.group(name="peer", context_settings={"help_option_names": ["-h", "--help"]})
def peer():
    """Add and sync trusted server-to-server federation peers."""


@peer.command()
@click.option("--name", required=True, help="Human-readable peer name.")
@click.option("--url", required=True, help="Peer base URL (e.g. https://peer.example).")
@click.option("--key", default=None, help="Peer public key to pin (trust-on-first-use).")
@click.option("--token", default=None, help="Bearer token sent when syncing with the peer.")
def add(name, url, key, token):
    """Register a trusted peer."""
    federation = _federation()
    new_peer = federation.add_peer(name=name, base_url=url, public_key=key, token=token)
    click.secho(
        f"Added peer {new_peer['id']} ({new_peer['name']}) -> {new_peer['base_url']}",
        fg="green",
    )


@peer.command(name="list")
def list_cmd():
    """List all trusted peers."""
    federation = _federation()
    rows = federation.list_peers()["records"]
    if not rows:
        click.echo("No peers found.")
        return

    header = f"{'ID':<18} {'NAME':<24} {'ACTIVE':<7} {'LAST_SYNC':<22} BASE_URL"
    click.echo(header)
    click.echo("-" * len(header))
    for p in rows:
        active = "yes" if p.get("active") else "no"
        click.echo(
            f"{(p.get('id') or ''):<18} "
            f"{(p.get('name') or ''):<24} "
            f"{active:<7} "
            f"{(p.get('last_sync_at') or '-'):<22} "
            f"{p.get('base_url') or ''}"
        )


@peer.command()
@click.argument("peer_id")
def remove(peer_id):
    """Remove a trusted peer by id."""
    federation = _federation()
    federation.remove_peer(peer_id)
    click.secho(f"Removed peer {peer_id}.", fg="green")


@peer.command()
@click.argument("peer_id")
def sync(peer_id):
    """Pull then push records with a trusted peer."""
    federation = _federation()
    result = federation.sync_peer(peer_id)
    click.echo(f"pull: {result['pull']}")
    click.echo(f"push: {result['push']}")

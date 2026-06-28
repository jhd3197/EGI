"""``egi shelter`` — manage shelters and verified-operator tokens (plan-20 §9).

Thin Click wrappers over ``server/modules/shelters.py``. This is where a
commander generates and revokes the one-time tokens a shelter operator redeems
to claim their shelter. Every callback pins the server DB via
``ensure_server_importable()`` first, so the CLI touches the same DB as a
running ``egi backend``.
"""

import click


def _shelters():
    """Import the server shelters module lazily (after pinning DB_PATH)."""
    from ..paths import ensure_server_importable

    ensure_server_importable()
    from modules import shelters  # noqa: E402

    return shelters


def _models():
    from ..paths import ensure_server_importable

    ensure_server_importable()
    import models  # noqa: E402

    return models


@click.group(name="shelter", context_settings={"help_option_names": ["-h", "--help"]})
def shelter():
    """Create shelters and manage verified-operator claim tokens."""


@shelter.command(name="list")
@click.option("--disaster", "disaster_id", default=None, help="Filter by disaster id.")
def list_cmd(disaster_id):
    """List shelters (optionally for one disaster)."""
    shelters = _shelters()
    rows = shelters.list_shelters(disaster_id)["records"]
    if not rows:
        click.echo("No shelters found.")
        return
    header = f"{'ID':<22} {'KIND':<9} {'TRUST':<10} {'ACCEPT':<7} NAME"
    click.echo(header)
    click.echo("-" * len(header))
    for s in rows:
        accept = "yes" if s.get("accepting_new") else "no"
        click.echo(
            f"{(s.get('id') or ''):<22} {(s.get('kind') or ''):<9} "
            f"{(s.get('trust') or ''):<10} {accept:<7} {s.get('name') or ''}"
        )


@shelter.command()
@click.option("--name", required=True, help="Shelter name.")
@click.option("--disaster", "disaster_id", default=None, help="Disaster id.")
@click.option("--kind", default="refugio", type=click.Choice(["refugio", "hospital"]))
@click.option("--lat", type=float, default=None)
@click.option("--lon", type=float, default=None)
def create(name, disaster_id, kind, lat, lon):
    """Create a shelter record."""
    shelters = _shelters()
    models = _models()
    rec = models.ShelterRecord(name=name, disaster_id=disaster_id, kind=kind, lat=lat, lon=lon)
    result = shelters.upsert_shelter(rec)
    click.secho(f"Created shelter {result['id']} ({result['name']})", fg="green")


@shelter.command(name="issue-token")
@click.argument("shelter_id")
@click.option("--label", default=None, help="A note describing who the token is for.")
@click.option("--by", "issued_by", default="cli:commander", help="Audit principal issuing the token.")
def issue_token(shelter_id, label, issued_by):
    """Mint a one-time claim token for a shelter. Shown ONCE."""
    shelters = _shelters()
    models = _models()
    result = shelters.issue_token(shelter_id, models.ShelterTokenCreate(label=label), issued_by)
    if result is None:
        click.secho(f"Shelter {shelter_id} not found.", fg="red")
        raise SystemExit(1)
    click.secho("Shelter claim token (copy now — shown only once):", fg="yellow")
    click.echo(result["token"])


@shelter.command(name="tokens")
@click.argument("shelter_id")
def tokens(shelter_id):
    """List issued tokens for a shelter (hints only, never the raw token)."""
    shelters = _shelters()
    rows = shelters.list_tokens(shelter_id)["records"]
    if not rows:
        click.echo("No tokens issued.")
        return
    header = f"{'HINT':<10} {'REVOKED':<8} {'CLAIMED_BY':<16} {'CREATED':<22} LABEL"
    click.echo(header)
    click.echo("-" * len(header))
    for tk in rows:
        click.echo(
            f"{(tk.get('token_hint') or ''):<10} "
            f"{('yes' if tk.get('revoked') else 'no'):<8} "
            f"{(tk.get('claimed_by_user_id') or '-'):<16} "
            f"{(tk.get('created_at') or ''):<22} {tk.get('label') or ''}"
        )


@shelter.command(name="revoke-token")
@click.argument("shelter_id")
@click.argument("token_hint")
def revoke_token(shelter_id, token_hint):
    """Revoke a token by its hint (the prefix shown in `egi shelter tokens`)."""
    shelters = _shelters()
    if shelters.revoke_token(token_hint, shelter_id):
        click.secho("Token revoked.", fg="green")
    else:
        click.secho("Token not found.", fg="red")
        raise SystemExit(1)


@shelter.command()
@click.argument("shelter_id")
def roster(shelter_id):
    """Print the check-in roster for a shelter (operator handover)."""
    shelters = _shelters()
    rows = shelters.roster(shelter_id)
    if not rows:
        click.echo("No check-ins.")
        return
    for r in rows:
        click.echo(f"{r.get('created_at', ''):<22} {r.get('alias') or '(sin alias)':<24} {r.get('note') or ''}")
